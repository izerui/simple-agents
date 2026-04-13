"""StreamingClient 模型配置集成测试.

这个文件关注“不同 provider / model 配置下，流式事件接口是否保持一致”。
"""

import asyncio
import uuid

import pytest
from langgraph_sdk.schema import Config

from src.clients import MessageEvent, RunEvent, StreamingClient, ToolEvent
from src.clients.handlers import StreamingEventHandlers


@pytest.mark.asyncio
class TestModelConfigStreamingIntegration:
    """模型配置维度.

    关注：
    - OpenAI 兼容 provider 配置是否可直接透传
    - 切模型后自定义 handler 使用方式是否不变
    """

    class ModelConfigPrintHandler(StreamingEventHandlers):
        async def on_run_started(self, event: RunEvent) -> None:
            print(f"[on_run_started] thread_id={event.thread_id} run_id={event.run_id}")

        async def on_message_streaming(self, event: MessageEvent) -> None:
            if event.delta:
                print(event.delta, end="", flush=True)

        async def on_message_completed(self, event: MessageEvent) -> None:
            print(f"\n[on_message_completed] message_id={event.message_id}")

        async def on_tool_pending(self, event: ToolEvent) -> None:
            print(f"[on_tool_pending] tool_name={event.tool_name}")

        async def on_tool_streaming_args(self, event: ToolEvent) -> None:
            if event.args_delta:
                print(event.args_delta, end="", flush=True)

        async def on_tool_running(self, event: ToolEvent) -> None:
            print("\n[on_tool_running]")

        async def on_tool_completed(self, event: ToolEvent) -> None:
            print(
                f"\n[on_tool_completed] status={event.status} tool_name={event.tool_name} "
                f"args_current={event.args_current!r} result_current={event.result_current!r}"
            )

        async def on_run_completed(self, event: RunEvent) -> None:
            print(f"[on_run_completed] thread_id={event.thread_id} run_id={event.run_id}")

        async def on_run_failed(self, event: RunEvent) -> None:
            print(f"[on_run_failed] thread_id={event.thread_id} run_id={event.run_id} error={event.error!r}")

    async def test_openai_compatible(self):
        host = "https://dev-dcca.hhstu.edu.cn/agent"
        assistant_id = "research"

        user_message = "你是什么大模型?"

        config = Config(
            configurable={
                "model_provider": "openai",
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "model": "qwen3-max",
                "max_input_tokens": 3000,
            }
        )

        thread_id = str(uuid.uuid4())
        client = StreamingClient(url=host, assistant_id=assistant_id)
        handler = self.ModelConfigPrintHandler()

        print(f"用户输入: {user_message}")
        print(f"线程ID: {thread_id}")
        print("-" * 40)

        await handler.consume(
            client.chat_stream(
                message=user_message,
                config=config,
                thread_id=thread_id,
                metadata={"user_id": "user001", "name": "测试动态模型切换"},
            )
        )

        print("\n" + "=" * 40)
        print("✅ 任务执行完成！")
        print("=" * 40)


if __name__ == "__main__":
    asyncio.run(TestModelConfigStreamingIntegration().test_openai_compatible())
