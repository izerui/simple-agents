"""规范化事件处理器.

客户端使用建议：

1. 增量回调（会重复触发，适合做流式内容更新）
   - on_message_streaming: assistant 正文增量
   - on_tool_streaming_args: 工具参数增量

2. 阶段回调（通常只在阶段切换时触发一次，适合做状态更新）
   - on_run_started / on_run_completed / on_run_failed
   - on_message_completed
   - on_tool_pending / on_tool_running / on_tool_completed
   - on_custom

使用规则：
- 只在 `streaming` 回调里做“内容追加/覆盖”
- 不要在 `completed/pending/running/started/failed` 回调里重复追加内容
- `completed` 类回调更适合做“节点收尾、状态落盘、最终结果更新”
"""

from __future__ import annotations

from typing import AsyncIterable

from .client import (
    CustomEvent,
    MessageEvent,
    RunEvent,
    StreamingEvent,
    ToolEvent,
)


class StreamingEventHandlers:
    """事件处理器基类.

    推荐用法：

    ```python
    class MyHandler(StreamingEventHandlers):
        async def on_message_streaming(self, event):
            # 这里只处理正文流式内容
            ...

        async def on_tool_pending(self, event):
            # 这里只创建工具节点
            ...

        async def on_tool_completed(self, event):
            # 这里只处理工具最终状态
            ...
    ```

    设计目标：
    - client 负责把原始 chunk 解析为规范化事件
    - handler 只负责消费规范化事件
    - 客户端通过覆写少数几个阶段方法即可完成接入
    """

    async def consume(self, events: AsyncIterable[StreamingEvent]) -> None:
        """顺序消费一个规范化事件流."""
        async for event in events:
            await self.handle(event)

    async def handle(self, event: StreamingEvent) -> None:
        """处理单个规范化事件并分发到对应阶段方法.

        分发规则：
        - RunEvent    -> on_run_started / on_run_completed / on_run_failed
        - MessageEvent -> on_message_streaming / on_message_completed
        - ToolEvent   -> on_tool_pending / on_tool_streaming_args / on_tool_running / on_tool_completed
        - CustomEvent -> on_custom
        """
        if isinstance(event, RunEvent):
            # run 事件是“整轮请求”的生命周期。
            if event.status == "started":
                await self.on_run_started(event)
            elif event.status == "completed":
                await self.on_run_completed(event)
            elif event.status == "failed":
                await self.on_run_failed(event)
            return

        if isinstance(event, MessageEvent):
            # message 事件只保留最常用的“流式中/已完成”两个阶段。
            if event.status == "streaming":
                await self.on_message_streaming(event)
            elif event.status == "completed":
                await self.on_message_completed(event)
            return

        if isinstance(event, ToolEvent):
            # tool 事件只暴露稳定阶段，不让调用端接触底层匿名/抖动状态。
            if event.status == "pending":
                await self.on_tool_pending(event)
            elif event.status == "streaming_args":
                await self.on_tool_streaming_args(event)
            elif event.status == "running":
                await self.on_tool_running(event)
            elif event.status in {"success", "failed", "streaming_result"}:
                await self.on_tool_completed(event)
            return

        if isinstance(event, CustomEvent):
            await self.on_custom(event)
            return

    async def on_run_started(self, event: RunEvent) -> None:
        """一轮请求开始.

        用途：
        - 设置“本轮请求开始中/执行中”状态
        - 初始化本轮运行上下文

        注意：
        - 这是阶段回调，不是流式内容回调
        - 不要在这里追加正文内容
        """
        return None

    async def on_run_completed(self, event: RunEvent) -> None:
        """一轮请求正常结束.

        用途：
        - 清理“执行中”状态
        - 标记本轮完成
        - 做整轮级别的收尾处理

        注意：
        - 这是阶段回调
        - 不负责追加正文内容
        """
        return None

    async def on_run_failed(self, event: RunEvent) -> None:
        """一轮请求失败结束.

        用途：
        - 标记本轮失败
        - 读取 `event.error` 展示错误信息
        - 做失败兜底收尾

        注意：
        - 这是整轮 run 级别的失败，不是单个 token 的问题
        """
        return None

    async def on_message_streaming(self, event: MessageEvent) -> None:
        """assistant 正文流式增量.

        这是“正文流式打字”的主回调，会重复触发。

        典型用途：
        - 追加/覆盖当前 assistant 消息内容
        - 实时渲染打字效果

        重点字段：
        - event.delta: 本次新增文本
        - event.current: 当前这条消息的累计文本
        """
        return None

    async def on_message_completed(self, event: MessageEvent) -> None:
        """当前 assistant 消息结束.

        用途：
        - 标记当前消息完成
        - 做消息级收尾

        注意：
        - 这是阶段回调
        - 不建议在这里重复追加正文内容
        - 正文内容应主要在 `on_message_streaming` 中处理
        """
        return None

    async def on_tool_pending(self, event: ToolEvent) -> None:
        """工具节点已稳定识别，可正式创建.

        典型用途：
        - 在客户端创建工具节点
        - 初始化工具状态

        说明：
        - 只有当 SDK 认为工具身份已经稳定后，才会触发这个回调
        - `on_tool_pending` 一定早于 `on_tool_streaming_args`
        """
        return None

    async def on_tool_streaming_args(self, event: ToolEvent) -> None:
        """工具参数流式增量.

        这是“工具参数流式展示”的主回调，会重复触发。

        典型用途：
        - 追加/覆盖工具参数显示
        - 实时展示模型正在构造的工具调用参数

        重点字段：
        - event.args_delta: 本次新增参数片段
        - event.args_current: 当前累计参数

        注意：
        - 只在这里做参数内容更新
        - 不要在 `on_tool_completed` 里重复拼接参数
        """
        return None

    async def on_tool_running(self, event: ToolEvent) -> None:
        """工具开始执行.

        用途：
        - 将工具节点状态切换为“执行中”
        - 结束参数编辑阶段，进入执行阶段

        注意：
        - 这是阶段回调，不是结果流式回调
        """
        return None

    async def on_tool_completed(self, event: ToolEvent) -> None:
        """工具调用结束.

        成功和失败都会进入这里，最终状态由 `event.status` 决定：
        - success
        - failed

        典型用途：
        - 更新工具最终状态
        - 写入最终结果 `event.result_current`
        - 失败时读取 `event.error`

        注意：
        - 这是阶段回调
        - 工具结果以最终结果为主，不建议在这里做增量拼接
        """
        return None

    async def on_custom(self, event: CustomEvent) -> None:
        """后端自定义事件.

        SDK 不解释业务语义，原样透传给客户端。
        """
        return None


class SimpleStreamingEventHandlers(StreamingEventHandlers):
    """默认打印型处理器."""

    async def on_message_streaming(self, event: MessageEvent) -> None:
        if event.delta:
            # 这里只打印 delta，模拟终端逐字输出。
            print(f"[on_message_streaming] {event.delta}", end="", flush=True)

    async def on_message_completed(self, event: MessageEvent) -> None:
        # message 收尾时只打印标记，不重复打印 current。
        print(f"\n[on_message_completed] message_id={event.message_id}")

    async def on_tool_pending(self, event: ToolEvent) -> None:
        print(f"\n\n[on_tool_pending] tool_name={event.tool_name}")
        if event.tool_call_id:
            print(f"[on_tool_pending] tool_call_id={event.tool_call_id}")

    async def on_tool_streaming_args(self, event: ToolEvent) -> None:
        if event.args_delta:
            # 参数阶段和正文阶段一样，只消费增量，避免 current 重复打印。
            print(f"[on_tool_streaming_args] {event.args_delta}", end="", flush=True)

    async def on_tool_running(self, event: ToolEvent) -> None:
        print("\n[on_tool_running]")

    async def on_tool_completed(self, event: ToolEvent) -> None:
        # 工具完成时统一打印最终状态和累计值，便于排查阶段是否完整。
        print(
            f"\n[on_tool_completed] status={event.status} tool_name={event.tool_name} "
            f"tool_call_id={event.tool_call_id} args_current={event.args_current!r} "
            f"result_current={event.result_current!r} error={event.error!r}"
        )

    async def on_custom(self, event: CustomEvent) -> None:
        print(f"\n[on_custom] data={event.data}")

    async def on_run_started(self, event: RunEvent) -> None:
        print(f"[on_run_started] thread_id={event.thread_id} run_id={event.run_id}")

    async def on_run_completed(self, event: RunEvent) -> None:
        print(f"[on_run_completed] thread_id={event.thread_id} run_id={event.run_id}")

    async def on_run_failed(self, event: RunEvent) -> None:
        print(f"[on_run_failed] thread_id={event.thread_id} run_id={event.run_id} error={event.error!r}")
