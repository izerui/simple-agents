"""流式 API 客户端.

职责划分：

1. raw_chat_stream()
- 直接请求后端，返回原始 chunk 流
- 适合调试底层协议或特殊场景自定义处理

2. chat_stream()
- 在 raw_chat_stream() 基础上，把原始 chunk 解析成规范化事件流
- 适合给 handler 或业务代码直接消费

设计原则：
- client 负责处理原始 chunk、缓存中间态、保证对外事件顺序稳定
- handler 只负责消费规范化事件，不处理底层 chunk 细节
"""

from __future__ import annotations

import base64
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Literal, Union

import aiofiles
import aiohttp
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph_sdk import get_client
from langgraph_sdk.schema import Config

logger = logging.getLogger(__name__)

FileType = Union[str, Path, dict]


class StreamingClientError(Exception):
    """SDK 基础异常.

    所有 clients SDK 相关异常的共同父类。
    """


class ClientConfigError(StreamingClientError):
    """客户端配置错误.

    典型场景：
    - thread_id 缺失
    - 参数组合非法
    """


class ThreadError(StreamingClientError):
    """线程相关错误.

    典型场景：
    - reset_thread 调用失败
    - 线程管理接口返回异常
    """


class StreamProtocolError(StreamingClientError):
    """流协议解析错误.

    典型场景：
    - 原始 chunk 结构不符合预期
    - 缺少关键字段导致无法归一化为稳定事件
    """


class TransportError(StreamingClientError):
    """网络传输错误.

    典型场景：
    - 请求后端失败
    - 网络连接异常
    """


@dataclass(slots=True, kw_only=True)
class BaseEvent:
    """所有规范化事件的基础字段.

    字段说明：
    - type: 事件类型
    - timestamp: 事件创建时间
    - thread_id: 当前对话线程 ID
    - run_id: 当前请求对应的运行 ID
    - metadata: 原始流中携带的元数据
    """

    type: str
    timestamp: float
    thread_id: str
    run_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, kw_only=True)
class RunEvent(BaseEvent):
    """运行生命周期事件.

    status:
    - started: 一轮请求开始
    - completed: 一轮请求正常结束
    - failed: 一轮请求失败结束
    """

    type: Literal["run"] = "run"
    status: Literal["started", "completed", "failed"] = "started"
    error: str | None = None


@dataclass(slots=True, kw_only=True)
class MessageEvent(BaseEvent):
    """assistant 正文消息事件.

    status:
    - streaming: 正文增量输出中
    - completed: 当前这条 assistant 消息结束
    - failed: 当前消息失败（当前版本暂未主动对外触发）

    字段说明：
    - message_id: 当前 assistant 消息的稳定标识
    - delta: 本次新增的正文片段
    - current: 当前这条消息的累计正文
    """

    type: Literal["message"] = "message"
    message_id: str = ""
    status: Literal["streaming", "completed", "failed"] = "streaming"
    delta: str = ""
    current: str = ""
    error: str | None = None


@dataclass(slots=True, kw_only=True)
class ToolEvent(BaseEvent):
    """工具阶段事件.

    status:
    - pending: 工具节点已稳定识别，可正式创建
    - streaming_args: 工具参数流式输出中
    - running: 工具开始执行
    - streaming_result: 工具结果增量中（当前后端一般很少出现）
    - success: 工具执行成功结束
    - failed: 工具执行失败结束

    字段说明：
    - tool_call_id: 工具调用 ID，有则透传，没有不强求
    - stream_id/stream_index: 用于在缺失 tool_call_id 时辅助关联
    - args_delta/args_current: 参数增量与累计值
    - result_delta/result_current: 结果增量与累计值
    """

    type: Literal["tool"] = "tool"
    tool_name: str = ""
    status: Literal[
        "pending", "streaming_args", "running", "streaming_result", "success", "failed"
    ] = "pending"
    tool_call_id: str | None = None
    stream_id: str | None = None
    stream_index: int | None = None
    args_delta: str = ""
    args_current: str = ""
    result_delta: str = ""
    result_current: str = ""
    error: str | None = None


@dataclass(slots=True, kw_only=True)
class CustomEvent(BaseEvent):
    """后端自定义事件.

    SDK 不解释业务语义，原样透传。
    """

    type: Literal["custom"] = "custom"
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, kw_only=True)
class ErrorEvent(BaseEvent):
    """底层错误事件.

    当前 handler 默认不直接消费该事件，而是最终以 RunEvent.failed 体现失败结果。
    保留这个事件模型，便于后续需要时扩展更细的错误通道。
    """

    type: Literal["error"] = "error"
    error: str = ""
    raw: Any = None


StreamingEvent = RunEvent | MessageEvent | ToolEvent | CustomEvent | ErrorEvent


@dataclass(slots=True)
class _ToolState:
    """SDK 内部使用的工具状态缓存.

    只用于 chunk -> 规范化事件的解析过程，不对外暴露。
    """

    tool_name: str
    stream_id: str
    stream_index: int | None
    tool_call_id: str | None = None
    args_current: str = ""
    result_current: str = ""
    identity_announced: bool = False
    running_announced: bool = False


class _EventParser:
    """原始 chunk 解析器.

    职责：
    - 读取 raw chunk
    - 缓存消息正文累计值
    - 缓存匿名工具参数片段
    - 在工具身份稳定后补发缓存参数
    - 按稳定顺序产出规范化事件

    注意：
    - 这是 client 内部协议层，不给业务代码直接使用
    """

    def __init__(self, thread_id: str):
        self.thread_id = thread_id
        self.run_id: str | None = None
        self._run_started = False
        self._active_messages: dict[str, str] = {}
        self._tool_states: dict[str, _ToolState] = {}
        self._anon_tool_args: dict[tuple[str, int | None], list[str]] = {}

    def _now(self) -> float:
        return time.time()

    def _base_metadata(self, metadata: dict[str, Any] | None) -> dict[str, Any]:
        return dict(metadata or {})

    def _build_run_event(
        self,
        *,
        status: Literal["started", "completed", "failed"],
        metadata: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> RunEvent:
        return RunEvent(
            timestamp=self._now(),
            thread_id=self.thread_id,
            run_id=self.run_id,
            metadata=self._base_metadata(metadata),
            status=status,
            error=error,
        )

    def _build_message_event(
        self,
        *,
        message_id: str,
        status: Literal["streaming", "completed", "failed"],
        metadata: dict[str, Any] | None = None,
        delta: str = "",
        current: str = "",
        error: str | None = None,
    ) -> MessageEvent:
        return MessageEvent(
            timestamp=self._now(),
            thread_id=self.thread_id,
            run_id=self.run_id,
            metadata=self._base_metadata(metadata),
            message_id=message_id,
            status=status,
            delta=delta,
            current=current,
            error=error,
        )

    def _build_tool_event(
        self,
        *,
        state: _ToolState,
        status: Literal["pending", "streaming_args", "running", "streaming_result", "success", "failed"],
        metadata: dict[str, Any] | None = None,
        args_delta: str = "",
        result_delta: str = "",
        error: str | None = None,
    ) -> ToolEvent:
        return ToolEvent(
            timestamp=self._now(),
            thread_id=self.thread_id,
            run_id=self.run_id,
            metadata=self._base_metadata(metadata),
            tool_name=state.tool_name,
            status=status,
            tool_call_id=state.tool_call_id,
            stream_id=state.stream_id,
            stream_index=state.stream_index,
            args_delta=args_delta,
            args_current=state.args_current,
            result_delta=result_delta,
            result_current=state.result_current,
            error=error,
        )

    def _state_key(self, tool_call_id: str | None, stream_id: str, stream_index: int | None) -> str:
        # 优先使用后端给出的稳定 tool_call_id；缺失时回退到消息内位置键。
        if tool_call_id:
            return f"id:{tool_call_id}"
        return f"stream:{stream_id}:{stream_index}"

    def _register_tool_state(
        self,
        *,
        tool_name: str,
        stream_id: str,
        stream_index: int | None,
        tool_call_id: str | None,
    ) -> _ToolState:
        key = self._state_key(tool_call_id, stream_id, stream_index)
        state = self._tool_states.get(key)
        if state is None:
            state = _ToolState(
                tool_name=tool_name,
                stream_id=stream_id,
                stream_index=stream_index,
                tool_call_id=tool_call_id,
            )
            self._tool_states[key] = state
        else:
            state.tool_name = tool_name or state.tool_name
            state.tool_call_id = tool_call_id or state.tool_call_id
            if state.stream_index is None:
                state.stream_index = stream_index
        return state

    def _find_tool_state(
        self,
        *,
        tool_call_id: str | None,
        stream_id: str,
        stream_index: int | None,
        tool_name: str | None = None,
    ) -> _ToolState | None:
        # 先按 tool_call_id 精确命中；命不中再退化到同一消息内的 stream_index 关联。
        if tool_call_id:
            state = self._tool_states.get(self._state_key(tool_call_id, stream_id, stream_index))
            if state is not None:
                return state
            for candidate in self._tool_states.values():
                if candidate.tool_call_id == tool_call_id:
                    return candidate
        for candidate in self._tool_states.values():
            if candidate.stream_id == stream_id and candidate.stream_index == stream_index:
                return candidate
        if tool_name:
            for candidate in self._tool_states.values():
                if candidate.tool_name == tool_name and candidate.stream_id == stream_id:
                    return candidate
        return None

    def _should_use_initial_args(self, initial_args: str, tool_call_chunks: list[dict[str, Any]]) -> bool:
        if not initial_args:
            return False
        if not tool_call_chunks:
            return True
        # 某些模型会先在 tool_calls.args 放一个占位对象，再从 chunks 重新输出完整 JSON。
        return not any(str(chunk.get("args", "")).strip() for chunk in tool_call_chunks)

    def _normalize_args(self, raw_args: Any) -> str:
        if isinstance(raw_args, str):
            return raw_args
        if isinstance(raw_args, dict):
            return "" if not raw_args else json.dumps(raw_args, ensure_ascii=False)
        if isinstance(raw_args, list):
            return "" if not raw_args else json.dumps(raw_args, ensure_ascii=False)
        return ""

    def _ensure_run_started(self, metadata: dict[str, Any] | None) -> list[StreamingEvent]:
        """确保 run.started 只发一次."""
        events: list[StreamingEvent] = []
        if metadata:
            if not self.run_id:
                self.run_id = metadata.get("run_id") or self.run_id
            if not self._run_started and self.run_id:
                self._run_started = True
                events.append(self._build_run_event(status="started", metadata=metadata))
        return events

    def process_chunk(self, chunk: Any) -> list[StreamingEvent]:
        """把一个原始 chunk 解析成 0..n 个规范化事件.

        对外顺序保证：
        - 事件顺序按可消费顺序输出
        - 工具匿名参数会先缓存，等身份稳定后再补发
        """
        event_name = getattr(chunk, "event", None)
        data = getattr(chunk, "data", None)
        if event_name is None:
            return []

        events: list[StreamingEvent] = []
        if event_name == "metadata" and isinstance(data, dict):
            self.run_id = data.get("run_id") or self.run_id
            events.extend(self._ensure_run_started(data))
            return events

        if event_name == "custom" and isinstance(data, dict):
            events.extend(self._ensure_run_started(data))
            events.append(
                CustomEvent(
                    timestamp=self._now(),
                    thread_id=self.thread_id,
                    run_id=self.run_id,
                    metadata=self._base_metadata(data),
                    data=data,
                )
            )
            return events

        if event_name != "messages":
            return events

        if not isinstance(data, list) or len(data) < 2:
            raise StreamProtocolError(f"Unexpected messages payload: {data!r}")

        msg_list = data[0]
        metadata = data[1] if isinstance(data[1], dict) else {}
        events.extend(self._ensure_run_started(metadata))

        if not isinstance(msg_list, list):
            msg_list = [msg_list]

        for msg in msg_list:
            if not isinstance(msg, dict):
                continue
            msg_type = msg.get("type")
            if msg_type == "AIMessageChunk":
                events.extend(self._process_ai_message(msg, metadata))
            elif msg_type == "tool":
                events.extend(self._process_tool_message(msg, metadata))
        return events

    def _process_ai_message(self, msg: dict[str, Any], metadata: dict[str, Any]) -> list[StreamingEvent]:
        """处理 AIMessageChunk.

        负责：
        - 正文 delta/current 累计
        - tool_calls 身份识别
        - tool_call_chunks 参数增量归并
        - message completed 事件
        """
        events: list[StreamingEvent] = []
        message_id = str(msg.get("id") or "")
        if not message_id:
            raise StreamProtocolError(f"AIMessageChunk missing id: {msg!r}")

        content = msg.get("content", "")
        if content:
            # message.current 只累计当前这条 assistant message，不跨 message_id 合并。
            current = self._active_messages.get(message_id, "") + str(content)
            self._active_messages[message_id] = current
            events.append(
                self._build_message_event(
                    message_id=message_id,
                    status="streaming",
                    metadata=metadata,
                    delta=str(content),
                    current=current,
                )
            )

        tool_call_chunks = msg.get("tool_call_chunks") or []

        for fallback_index, tc in enumerate(msg.get("tool_calls") or []):
            if not isinstance(tc, dict):
                continue
            tool_name = str(tc.get("name") or "").strip()
            tool_call_id = str(tc.get("id") or "").strip() or None
            stream_index = tc.get("index", fallback_index)
            normalized_args = self._normalize_args(tc.get("args"))
            if not tool_name:
                continue
            state = self._register_tool_state(
                tool_name=tool_name,
                stream_id=message_id,
                stream_index=stream_index,
                tool_call_id=tool_call_id,
            )
            if not state.identity_announced and (tool_call_id or stream_index is not None):
                # 只有工具身份稳定后，才正式对外暴露工具节点。
                state.identity_announced = True
                events.append(self._build_tool_event(state=state, status="pending", metadata=metadata))
                if self._should_use_initial_args(normalized_args, tool_call_chunks):
                    state.args_current += normalized_args
                    if normalized_args:
                        events.append(
                            self._build_tool_event(
                                state=state,
                                status="streaming_args",
                                metadata=metadata,
                                args_delta=normalized_args,
                            )
                        )
                # 之前匿名到达的参数增量，此时按原始顺序补发给调用端。
                buffered = self._anon_tool_args.pop((message_id, stream_index), [])
                for args_delta in buffered:
                    state.args_current += args_delta
                    events.append(
                        self._build_tool_event(
                            state=state,
                            status="streaming_args",
                            metadata=metadata,
                            args_delta=args_delta,
                        )
                    )

        for tcc in tool_call_chunks:
            if not isinstance(tcc, dict):
                continue
            args_delta = str(tcc.get("args") or "")
            if not args_delta:
                continue
            tool_name = str(tcc.get("name") or "").strip() or None
            tool_call_id = str(tcc.get("id") or "").strip() or None
            stream_index = tcc.get("index")
            state = None
            if tool_name and (tool_call_id or stream_index is not None):
                state = self._find_tool_state(
                    tool_call_id=tool_call_id,
                    stream_id=message_id,
                    stream_index=stream_index,
                    tool_name=tool_name,
                )
                if state is None:
                    state = self._register_tool_state(
                        tool_name=tool_name,
                        stream_id=message_id,
                        stream_index=stream_index,
                        tool_call_id=tool_call_id,
                    )
                if not state.identity_announced:
                    state.identity_announced = True
                    events.append(self._build_tool_event(state=state, status="pending", metadata=metadata))
                    buffered = self._anon_tool_args.pop((message_id, stream_index), [])
                    for buffered_delta in buffered:
                        state.args_current += buffered_delta
                        events.append(
                            self._build_tool_event(
                                state=state,
                                status="streaming_args",
                                metadata=metadata,
                                args_delta=buffered_delta,
                            )
                        )

            if state is None and stream_index is not None:
                state = self._find_tool_state(
                    tool_call_id=None,
                    stream_id=message_id,
                    stream_index=stream_index,
                )
                if state is None:
                    stream_candidates = [
                        candidate
                        for candidate in self._tool_states.values()
                        if candidate.stream_id == message_id and candidate.stream_index is None
                    ]
                    if len(stream_candidates) == 1:
                        state = stream_candidates[0]
                        state.stream_index = stream_index
                        if not state.identity_announced:
                            state.identity_announced = True
                            events.append(
                                self._build_tool_event(state=state, status="pending", metadata=metadata)
                            )
                        buffered = self._anon_tool_args.pop((message_id, stream_index), [])
                        for buffered_delta in buffered:
                            state.args_current += buffered_delta
                            events.append(
                                self._build_tool_event(
                                    state=state,
                                    status="streaming_args",
                                    metadata=metadata,
                                    args_delta=buffered_delta,
                                )
                            )

            if state is None:
                # 身份还不稳定时，先缓存参数片段，避免对外出现乱序事件。
                self._anon_tool_args.setdefault((message_id, stream_index), []).append(args_delta)
                continue

            state.args_current += args_delta
            events.append(
                self._build_tool_event(
                    state=state,
                    status="streaming_args",
                    metadata=metadata,
                    args_delta=args_delta,
                )
            )

        if msg.get("chunk_position") == "last":
            # 对调用端而言，message.completed 是“这条 assistant 消息结束”，不是整轮 run 结束。
            current = self._active_messages.pop(message_id, "")
            events.append(
                self._build_message_event(
                    message_id=message_id,
                    status="completed",
                    metadata=metadata,
                    current=current,
                )
            )

        return events

    def _process_tool_message(self, msg: dict[str, Any], metadata: dict[str, Any]) -> list[StreamingEvent]:
        """处理 tool 消息.

        当前策略：
        - 先发 running
        - 如有结果内容，更新 result_current
        - 再发最终 completed（success/failed）

        说明：
        - 当前后端通常不是结果流式，所以 completed 是主要最终结果出口
        """
        events: list[StreamingEvent] = []
        tool_name = str(msg.get("name") or "").strip()
        tool_call_id = str(msg.get("tool_call_id") or "").strip() or None
        content = str(msg.get("content") or "")
        raw_status = str(msg.get("status") or "").strip().lower()
        status: Literal["success", "failed"] = "success" if raw_status == "success" else "failed"

        state = self._find_tool_state(
            tool_call_id=tool_call_id,
            stream_id="",
            stream_index=None,
            tool_name=tool_name or None,
        )
        if state is None:
            # 即使前面没有成功建立 tool 节点，只要最终 tool message 稳定到了，也要补建节点。
            state = _ToolState(
                tool_name=tool_name or "unknown",
                stream_id="",
                stream_index=None,
                tool_call_id=tool_call_id,
                identity_announced=True,
            )
            self._tool_states[self._state_key(tool_call_id, state.stream_id, state.stream_index)] = state
            events.append(self._build_tool_event(state=state, status="pending", metadata=metadata))

        if not state.running_announced:
            # tool message 到达时，先显式切到 running，再给最终 completed。
            state.running_announced = True
            events.append(self._build_tool_event(state=state, status="running", metadata=metadata))

        if content:
            state.result_current += content
            events.append(
                self._build_tool_event(
                    state=state,
                    status="streaming_result",
                    metadata=metadata,
                    result_delta=content,
                )
            )

        events.append(
            self._build_tool_event(
                state=state,
                status=status,
                metadata=metadata,
                error=content if status == "failed" else None,
            )
        )
        return events


class StreamingClient:
    """流式 API 客户端.

    推荐使用方式：

    1. 直接消费事件流
    ```python
    async for event in client.chat_stream(...):
        ...
    ```

    2. 配合 handler 使用
    ```python
    await handler.consume(client.chat_stream(...))
    ```
    """

    def __init__(
        self,
        url: str = "http://localhost:2024",
        api_key: str = "",
        assistant_id: str = "research",
    ):
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.assistant_id = assistant_id
        self._client = get_client(url=self.url, api_key=api_key)

    async def chat_stream(
        self,
        message: str,
        files: list[FileType] | None = None,
        system_prompt: str | None = None,
        thread_id: str | None = None,
        config: Config | None = None,
        metadata: dict | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamingEvent]:
        """返回规范化事件流.

        这是主接口。

        调用方不需要关心原始 chunk 格式，只需要消费：
        - RunEvent
        - MessageEvent
        - ToolEvent
        - CustomEvent
        """
        if not thread_id:
            raise ClientConfigError("thread_id is required")

        parser = _EventParser(thread_id=thread_id)
        try:
            async for chunk in self.raw_chat_stream(
                message=message,
                files=files,
                system_prompt=system_prompt,
                thread_id=thread_id,
                config=config,
                metadata=metadata,
                **kwargs,
            ):
                # client 对外只暴露规范化事件，handler 不再接触原始 chunk。
                for event in parser.process_chunk(chunk):
                    yield event
            yield parser._build_run_event(status="completed")
        except StreamingClientError as exc:
            yield ErrorEvent(
                timestamp=time.time(),
                thread_id=thread_id,
                run_id=parser.run_id,
                metadata={},
                error=str(exc),
                raw=exc,
            )
            yield parser._build_run_event(status="failed", error=str(exc))
            raise
        except Exception as exc:
            error = StreamProtocolError(str(exc))
            yield ErrorEvent(
                timestamp=time.time(),
                thread_id=thread_id,
                run_id=parser.run_id,
                metadata={},
                error=str(error),
                raw=exc,
            )
            yield parser._build_run_event(status="failed", error=str(error))
            raise error from exc

    async def raw_chat_stream(
        self,
        message: str,
        files: list[FileType] | None = None,
        system_prompt: str | None = None,
        thread_id: str | None = None,
        config: Config | None = None,
        metadata: dict | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        """返回原始 chunk 流.

        适用场景：
        - 调试底层协议
        - 需要完全自定义 chunk 解析逻辑

        一般业务接入更推荐使用 `chat_stream()`。
        """
        if not thread_id:
            raise ClientConfigError("thread_id is required")

        processed_files = []
        if files:
            for item in files:
                if isinstance(item, dict):
                    # 已经是后端可接受的块结构，直接透传。
                    processed_files.append(item)
                elif isinstance(item, (str, Path)):
                    processed_files.append(await self._load_file(item))
                else:
                    logger.warning("Unknown file type: %s, skipping", type(item))

        messages: list[Any] = []
        if system_prompt:
            # system_prompt 作为“本轮请求级”输入附加，不做长期 thread 状态管理。
            messages.append(SystemMessage(content=system_prompt))

        content_blocks: list[dict[str, Any]] = [{"type": "text", "text": message}]
        content_blocks.extend(processed_files)
        messages.append(HumanMessage(content=content_blocks))

        try:
            chunks = self._client.runs.stream(
                thread_id=thread_id,
                assistant_id=self.assistant_id,
                input={"messages": messages},
                stream_mode=["messages-tuple", "custom"],
                config=config,
                metadata=metadata,
                if_not_exists="create",
                **kwargs,
            )
            async for chunk in chunks:
                yield chunk
        except aiohttp.ClientError as exc:
            raise TransportError(str(exc)) from exc

    async def reset_thread(self, thread_id: str) -> dict[str, Any]:
        """重置指定 thread.

        语义对齐后端 reset 接口：
        - 保留同一个 thread_id
        - 清空 thread 状态和相关沙箱内容
        - 用同一个 thread_id 重建线程
        """
        if not thread_id:
            raise ClientConfigError("thread_id is required")
        reset_url = f"{self.url}/reset/{thread_id}"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(reset_url) as response:
                    payload = await response.json(content_type=None)
                    if response.status >= 400:
                        raise ThreadError(f"reset_thread failed: {response.status} {payload}")
                    return {
                        "thread_id": thread_id,
                        "success": True,
                        "data": payload,
                    }
            except aiohttp.ClientError as exc:
                raise TransportError(str(exc)) from exc

    async def _load_file(self, file_path: Union[str, Path]) -> dict[str, Any]:
        """将输入文件统一转为后端可接收的消息块.

        规则：
        - 本地路径 -> 读取为 base64 `file`
        - URL 字符串 -> 透传为 `file_url`
        """
        path_str = str(file_path)
        if path_str.startswith(("http://", "https://")):
            # URL 走 file_url 透传，让后端中间件统一下载和落地。
            filename = path_str.split("/")[-1].split("?")[0] or "remote-file"
            return {
                "type": "file_url",
                "url": path_str,
                "metadata": {"filename": filename},
            }
        return await self._read_local_file(file_path)

    async def _read_local_file(self, file_path: Union[str, Path]) -> dict[str, Any]:
        """读取本地文件并转为 base64 文件块."""
        path = Path(file_path)
        filename = path.name
        async with aiofiles.open(path, "rb") as f:
            data = base64.b64encode(await f.read()).decode("utf-8")
        return {
            "type": "file",
            "data": data,
            "metadata": {"filename": filename},
        }
