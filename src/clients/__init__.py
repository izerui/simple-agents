"""流式 API 客户端 SDK.

提供简洁的接口来请求 LangGraph API 并处理各种流式事件。

示例用法:
    from src.clients import StreamingClient, EventHandlers

    client = StreamingClient("http://localhost:2024")
    handler = EventHandlers()
    async for chunk in client.stream_chat("你好"):
        await handler.receive_chunk(chunk)
"""

from .client import StreamingClient
from .handlers import EventHandlers

__all__ = [
    "StreamingClient",
    "EventHandlers",
]
