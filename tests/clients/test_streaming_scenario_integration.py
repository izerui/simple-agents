"""StreamingClient 流式场景集成测试."""

import asyncio
import os
import uuid

import pytest
from langgraph_sdk.schema import Config

from src.clients import MessageEvent, RunEvent, StreamingClient, ToolEvent
from src.clients.handlers import StreamingEventHandlers

TEST_DIR = os.path.dirname(os.path.abspath(__file__))


@pytest.mark.asyncio
class TestStreamingScenarioIntegration:
    """流式业务场景维度.

    关注：
    - 多文件输入
    - system_prompt 随请求传入
    - 自定义 handler 是否能完整消费事件流
    """

    class ScenarioPrintHandler(StreamingEventHandlers):
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

    async def test_paper_evaluation(self):
        host = "https://dev-dcca.hhstu.edu.cn/agent"
        assistant_id = "research"

        user_message = """读取markdown格式论文，基于论文指导手册，从专业角度评价该学生论文,写入到最终报告文件中。"""

        system_prompt = """# 你是一个本科毕业生的导师，以老师的角度进行分析"""

        files = [
            os.path.join(TEST_DIR, "张卓群毕业论文3.docx"),
            os.path.join(TEST_DIR, "HELP.md"),
        ]

        thread_id = str(uuid.uuid4())
        client = StreamingClient(url=host, assistant_id=assistant_id)
        handler = self.ScenarioPrintHandler()

        config = Config(
            configurable={
                "model_provider": "openai",
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "model": "qwen3-max",
            }
        )

        print(f"用户输入: {user_message[:50]}...")

        await handler.consume(
            client.chat_stream(
                message=user_message,
                files=files,
                system_prompt=system_prompt,
                thread_id=thread_id,
                multitask_strategy="reject",
                stream_subgraphs=True,
                on_disconnect="cancel",
                on_completion="keep",
                durability="async",
                metadata={"user_id": "user001", "name": "张卓群的论文评价"},
                config=config,
            )
        )

        print("\n" + "=" * 80)
        print("✅ 任务执行完成！")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(TestStreamingScenarioIntegration().test_paper_evaluation())
