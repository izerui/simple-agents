"""使用示例."""

import asyncio

from src.clients import MessageEvent, StreamingClient, StreamingEventHandlers
from src.clients.handlers import SimpleStreamingEventHandlers


async def example_basic():
    """基础用法：默认打印输出."""
    client = StreamingClient("http://localhost:2024")
    handler = SimpleStreamingEventHandlers()

    print("=" * 50)
    print("示例1: 基础用法")
    print("=" * 50)

    await handler.consume(
        client.chat_stream(
            message="你好，请介绍一下自己",
            thread_id="example-basic",
        )
    )


async def example_custom_handler():
    """示例2: 自定义处理器（继承类）."""

    class MyHandler(StreamingEventHandlers):
        async def on_message_streaming(self, event: MessageEvent) -> None:
            print(f"[AI] {event.delta}", end="")

        async def on_tool_completed(self, event) -> None:
            print(f"\n[工具] {event.tool_name}, 参数: {event.args_current[:50]}...")

    client = StreamingClient("http://localhost:2024")
    handler = MyHandler()

    print("=" * 50)
    print("示例2: 自定义处理器")
    print("=" * 50)

    await handler.consume(
        client.chat_stream(
            message="列出当前目录的文件",
            thread_id="example-custom",
        )
    )


async def example_with_files():
    """示例3: 带文件上传."""
    client = StreamingClient("http://localhost:2024")
    handler = SimpleStreamingEventHandlers()

    print("=" * 50)
    print("示例3: 带文件上传")
    print("=" * 50)

    await handler.consume(
        client.chat_stream(
            message="请分析这个文件",
            files=["example.pdf"],
            thread_id="example-files",
        )
    )


if __name__ == "__main__":
    asyncio.run(example_basic())
