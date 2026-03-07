"""事件处理器.

提供默认的事件处理器，可继承并覆盖方法来实现自定义处理。

解析逻辑:
- 遍历原始 chunk 数据
- 根据 chunk.event 分发事件
- 触发流式事件: on_ai_message_chunk, on_tool_call_start, on_tool_call_args_chunk, on_tool_result_chunk
- 累积参数，触发完成事件: on_tool_call_complete
"""

import logging
from abc import abstractmethod, ABC
from typing import Any, override

logger = logging.getLogger(__name__)


class StreamingEventHandlers(ABC):
    """事件处理器基类.

    使用方式:
        handler = EventHandlers()
        async for chunk in client.stream_chat("你好"):
            await handler.receive_chunk(chunk)

    可继承并覆盖以下方法:
        - on_ai_message_chunk(content: str, is_chunk_start: bool)  # AI 文本流式
        - on_tool_call_start(tool_id, tool_name)  # 工具调用开始
        - on_tool_call_args_chunk(tool_id, args_chunk, is_chunk_start)  # 参数流式
        - on_tool_result_chunk(tool_id, content, is_chunk_start)  # 结果流式
        - on_tool_call_complete(tool_id, tool_name, args, content, status)  # 完整结果
        - on_custom(data: dict)  # 自定义事件
        - on_error(error: Exception)  # 错误
    """

    def __init__(self):
        # 工具调用注册表: {tool_id: {name, args}}
        self._tool_calls_registry: dict[str, dict] = {}
        # 标记：工具调用是否刚刚完成（用于 on_ai_message_chunk 换行判断）
        self._last_tool_call_ended: bool = False

    async def receive_chunk(self, chunk: Any):
        """接收原始 chunk，解析并分发事件."""
        try:
            event_name = chunk.event if hasattr(chunk, "event") else None
            data = chunk.data if hasattr(chunk, "data") else None
            if event_name is None:
                return

            # 自定义事件
            if event_name == "custom" and isinstance(data, dict):
                await self.on_custom(data)
                return

            # 消息事件
            if event_name == "messages":
                if not isinstance(data, list) or len(data) < 2:
                    return

                msg_list = data[0]
                if not isinstance(msg_list, list):
                    msg_list = [msg_list]

                for msg in msg_list:
                    if not isinstance(msg, dict):
                        continue
                    msg_type = msg.get("type")

                    if msg_type == "AIMessageChunk":
                        await self._handle_ai_message_chunk(msg)
                    elif msg_type == "tool":
                        await self._handle_tool_message(msg)

        except Exception as e:
            logger.error(f"Error processing chunk: {e}")
            await self.on_error(e)

    async def _handle_ai_message_chunk(self, msg: dict):
        """处理 AI 消息块."""
        content = msg.get("content", "")
        chunk_position = msg.get("chunk_position")
        is_message_end = chunk_position == "last"

        if content:
            # 工具调用完成后新一轮 AI 输出开始，需要换行
            is_chunk_start = self._last_tool_call_ended
            if is_chunk_start:
                self._last_tool_call_ended = False
            await self.on_ai_message_chunk(content, is_chunk_start, is_message_end)

        # tool_calls - 工具调用开始（args 为空，参数通过 tool_call_chunks 流式传递）
        tool_calls = msg.get("tool_calls", [])
        for idx, tc in enumerate(tool_calls):
            tool_name = tc.get("name", "")
            tool_id = tc.get("id", "")
            if tool_name and tool_id:
                self._tool_calls_registry[tool_id] = {
                    "name": tool_name,
                    "args": "",
                    "index": idx,  # 保存 index 用于 fallback 匹配
                }
                await self.on_tool_call_start(tool_id, tool_name)

        # tool_call_chunks - 参数流式
        tool_call_chunks = msg.get("tool_call_chunks", [])
        for tcc in tool_call_chunks:
            tcc_id = tcc.get("id", "")
            tcc_index = tcc.get("index")  # 获取 index
            args_chunk = tcc.get("args", "")

            # 累加参数：优先通过 ID，其次通过 index，最后通过 name
            matched_id = None
            is_args_chunk_start = False
            if tcc_id and tcc_id in self._tool_calls_registry:
                self._tool_calls_registry[tcc_id]["args"] += args_chunk
                matched_id = tcc_id
                # 检查是否是第一次参数
                if not hasattr(self, '_tool_args_started'):
                    self._tool_args_started = {}
                is_args_chunk_start = not self._tool_args_started.get(tcc_id, False)
                self._tool_args_started[tcc_id] = True
            elif tcc_index is not None:
                # 通过 index 匹配
                for tid, info in self._tool_calls_registry.items():
                    if info.get("index") == tcc_index:
                        self._tool_calls_registry[tid]["args"] += args_chunk
                        matched_id = tid
                        if not hasattr(self, '_tool_args_started'):
                            self._tool_args_started = {}
                        is_args_chunk_start = not self._tool_args_started.get(tid, False)
                        self._tool_args_started[tid] = True
                        break
            elif args_chunk:
                # 最后尝试通过 name 匹配
                name = tcc.get("name", "")
                for tid, info in self._tool_calls_registry.items():
                    if info.get("name") == name:
                        self._tool_calls_registry[tid]["args"] += args_chunk
                        matched_id = tid
                        if not hasattr(self, '_tool_args_started'):
                            self._tool_args_started = {}
                        is_args_chunk_start = not self._tool_args_started.get(tid, False)
                        self._tool_args_started[tid] = True
                        break

            # 无论是否找到匹配，都流式输出参数
            if args_chunk:
                await self.on_tool_call_args_chunk(matched_id or tcc_id, args_chunk, is_args_chunk_start)

    async def _handle_tool_message(self, msg: dict):
        """处理工具消息."""
        tool_name = msg.get("name", "unknown")
        tool_content = msg.get("content", "")
        tool_call_id = msg.get("tool_call_id", "")
        tool_status = msg.get("status")

        # 结果流式
        if tool_content:
            # 检查是否是第一次结果（用于 is_chunk_start）
            is_result_chunk_start = not hasattr(self, '_tool_result_started') or not self._tool_result_started.get(tool_call_id, False)
            if not hasattr(self, '_tool_result_started'):
                self._tool_result_started = {}
            self._tool_result_started[tool_call_id] = True

            await self.on_tool_result_chunk(tool_call_id, tool_content, is_result_chunk_start)
            # 标记工具调用已结束，下一次 AI 输出需要换行
            self._last_tool_call_ended = True

        # 完整结果（累积的参数 + 最终结果）
        args = ""
        if tool_call_id and tool_call_id in self._tool_calls_registry:
            tool_call_info = self._tool_calls_registry.pop(tool_call_id)
            args = tool_call_info.get("args", "")
            tool_name = tool_call_info.get("name", tool_name)

        await self.on_tool_call_complete(
            tool_id=tool_call_id,
            tool_name=tool_name,
            args=args,
            content=tool_content,
            status=tool_status,
        )

    # ========== 可覆盖的处理方法 ==========

    @abstractmethod
    async def on_ai_message_chunk(
        self, content: str, is_chunk_start: bool = False, is_message_end: bool = False
    ):
        """AI 文本流式输出.

        Args:
            content: AI 输出的文本
            is_chunk_start: 是否是工具调用完成后新一轮 chunk 开始（需要换行）
            is_message_end: 是否是整个消息流的最后一个 chunk
        """
        pass

    @abstractmethod
    async def on_tool_call_start(self, tool_id: str, tool_name: str):
        """工具调用开始."""
        pass

    @abstractmethod
    async def on_tool_call_args_chunk(self, tool_id: str, args_chunk: str, is_chunk_start: bool = False):
        """工具参数流式输出.

        Args:
            tool_id: 工具调用 ID
            args_chunk: 参数字符串片段
            is_chunk_start: 是否是参数流式开始
        """
        pass

    @abstractmethod
    async def on_tool_result_chunk(self, tool_id: str, content: str, is_chunk_start: bool = False):
        """工具结果流式输出.

        Args:
            tool_id: 工具调用 ID
            content: 工具返回的内容
            is_chunk_start: 是否是结果流式开始
        """
        pass

    @abstractmethod
    async def on_tool_call_complete(
        self,
        tool_id: str,
        tool_name: str,
        args: str,
        content: str,
        status: str | None,
    ):
        """工具调用完整结果.

        Args:
            tool_id: 工具调用 ID
            tool_name: 工具名称
            args: 完整参数
            content: 完整结果
            status: 执行状态
        """
        pass

    @abstractmethod
    async def on_custom(self, data: dict):
        """自定义事件."""
        pass

    @abstractmethod
    async def on_error(self, error: Exception):
        """错误事件."""
        pass


class SimpleStreamingEventHandlers(StreamingEventHandlers):

    async def on_ai_message_chunk(
        self, content: str, is_chunk_start: bool = False, is_message_end: bool = False
    ):
        """AI 文本流式输出.

        Args:
            content: AI 输出的文本
            is_chunk_start: 是否是工具调用完成后新一轮 chunk 开始（需要换行）
            is_message_end: 是否是整个消息流的最后一个 chunk
        """
        if content:
            if is_chunk_start:
                print("\n\n", end="")
            print(content, end="", flush=True)

    async def on_tool_call_start(self, tool_id: str, tool_name: str):
        """工具调用开始."""
        print(f"工具: {tool_name}")
        print(f"ID: {tool_id}")

    async def on_tool_call_args_chunk(self, tool_id: str, args_chunk: str, is_chunk_start: bool = False):
        """工具参数流式输出.

        Args:
            tool_id: 工具调用 ID
            args_chunk: 参数字符串片段
            is_chunk_start: 是否是参数流式开始
        """
        if args_chunk:
            if is_chunk_start:
                print("")
            print(f"{args_chunk}", end="", flush=True)

    async def on_tool_result_chunk(self, tool_id: str, content: str, is_chunk_start: bool = False):
        """工具结果流式输出.

        Args:
            tool_id: 工具调用 ID
            content: 工具返回的内容
            is_chunk_start: 是否是结果流式开始
        """
        # 截断显示
        if content:
            if is_chunk_start:
                print("")  # 换行
            print(f"{content}", end="", flush=True)

    async def on_tool_call_complete(
        self,
        tool_id: str,
        tool_name: str,
        args: str,
        content: str,
        status: str | None,
    ):
        """工具调用完整结果.

        Args:
            tool_id: 工具调用 ID
            tool_name: 工具名称
            args: 完整参数
            content: 完整结果
            status: 执行状态
        """
        print(f"\n\n🔧 ===== 工具调用完成 =====")
        print(f"工具: {tool_name}")
        print(f"ID: {tool_id}")
        if status:
            print(f"状态: {status}")
        # 截断显示
        display_args = args[:50] + "..." if len(args) > 50 else args
        display_content = content[:50] + "..." if len(content) > 50 else content
        print(f"参数: {display_args}")
        print(f"结果: {display_content}")
        print(f"===========================\n")

    async def on_custom(self, data: dict):
        """自定义事件."""
        print(f"\n🔔 自定义事件")
        print(f"   数据: {data}")

    async def on_error(self, error: Exception):
        """错误事件."""
        print(f"\n❌ 错误: {error}")