"""使用 StreamingClient SDK 的 file_url 测试函数."""

import asyncio
import os
import uuid

from langgraph_sdk.schema import Config

from src.clients import StreamingClient
from src.clients.handlers import SimpleStreamingEventHandlers


async def run_file_url_attachment():
    """测试: file_url 附件读取。"""
    host = "http://localhost:2024"
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
    handler = SimpleStreamingEventHandlers()

    config = Config(
        configurable={
            "model_provider": "openai",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            # "api_key": "sk-xxxxx",
            # "model": "deepseek-v3.2",
            # "model": "glm-4.7",
            # "model": "MiniMax-M2.1",
            "model": "qwen3-max",
        }
    )

    print(f"用户输入: {user_message}")
    print(f"URL 附件: {file_url}")

    async for chunk in client.chat_stream(
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
    ):
        await handler.receive_chunk(chunk)

    print("\n" + "=" * 80)
    print("✅ file_url 测试完成！")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_file_url_attachment())
