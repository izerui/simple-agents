"""StreamingClient 文件 URL 流式集成测试."""

import asyncio
import os
import uuid

import pytest
from langgraph_sdk.schema import Config

from src.clients import MessageEvent, RunEvent, StreamingClient, ToolEvent
from src.clients.handlers import StreamingEventHandlers


@pytest.mark.asyncio
class TestFileUrlStreamingIntegration:
    """文件 URL 透传维度.

    关注：
    - file_url 块是否能直接透传给后端
    - 自定义 handler 是否能完整消费带 URL 附件的事件流
    """

    class FileUrlPrintHandler(StreamingEventHandlers):
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

    async def test_file_url_attachment(self):
        host = "https://dev-dcca.hhstu.edu.cn/agent"
        assistant_id = "research"

        user_message = "请读取这个 URL 附件，并简要说明它的内容。"

        file_url = os.getenv(
            "TEST_FILE_URL",
            "https://ontheline.trincoll.edu/images/bookdown/sample-local-pdf.pdf",
        )

        files = [
            {
                "type": "file_url",
                "url": file_url,
                "metadata": {"filename": os.getenv("TEST_FILE_URL_NAME", "remote-file.pdf")},
                "mimeType": os.getenv("TEST_FILE_URL_MIME", "application/pdf"),
            }
        ]

        thread_id = str(uuid.uuid4())
        client = StreamingClient(url=host, assistant_id=assistant_id)
        handler = self.FileUrlPrintHandler()

        config = Config(
            configurable={
                "model_provider": "openai",
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "model": "qwen3-max",
            }
        )

        print(f"用户输入: {user_message}")
        print(f"URL 附件: {file_url}")

        await handler.consume(
            client.chat_stream(
                message=user_message,
                files=files,
                thread_id=thread_id,
                multitask_strategy="reject",
                stream_subgraphs=True,
                on_disconnect="cancel",
                on_completion="keep",
                durability="async",
                metadata={"user_id": "user001", "name": "file_url 附件测试"},
                config=config,
            )
        )

        print("\n" + "=" * 80)
        print("✅ file_url 测试完成！")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(TestFileUrlStreamingIntegration().test_file_url_attachment())
