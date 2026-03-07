"""使用示例."""

import asyncio
from src.clients import StreamingClient, StreamingEventHandlers
from src.clients.handlers import SimpleStreamingEventHandlers


async def example_basic():
    """基础用法：默认打印输出."""
    client = StreamingClient("http://localhost:2024")
    handler = SimpleStreamingEventHandlers()

    print("=" * 50)
    print("示例1: 基础用法")
    print("=" * 50)

    async for chunk in client.stream_chat("你好，请介绍一下自己"):
        await handler.receive_chunk(chunk)


async def example_custom_handler():
    """示例2: 自定义处理器（继承类）."""

    class MyHandler(StreamingEventHandlers):
        """自定义处理器."""

        async def on_ai_message_chunk(
            self, content: str, is_chunk_start: bool = False, is_message_end: bool = False
        ):
            print(f"[AI] {content}", end="")

        async def on_tool_call_complete(self, tool_id, tool_name, args, content, status):
            print(f"\n[工具] {tool_name}, 参数: {args[:50]}...")

    client = StreamingClient("http://localhost:2024")
    handler = MyHandler()

    print("=" * 50)
    print("示例2: 自定义处理器")
    print("=" * 50)

    async for chunk in client.stream_chat("列出当前目录的文件"):
        await handler.receive_chunk(chunk)


async def example_with_files():
    """示例3: 带文件上传."""
    client = StreamingClient("http://localhost:2024")
    handler = SimpleStreamingEventHandlers()

    print("=" * 50)
    print("示例3: 带文件上传")
    print("=" * 50)

    # 支持直接传入文件路径
    files = [
        "example.pdf",
    ]

    async for chunk in client.chat_stream(
        message="请分析这个文件",
        files=files,
    ):
        await handler.receive_chunk(chunk)


if __name__ == "__main__":
    asyncio.run(example_basic())
