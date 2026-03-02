"""流式 API 客户端.

使用方式:
    from src.clients import StreamingClient, EventHandlers

    handler = EventHandlers()
    async for chunk in client.stream_chat("你好"):
        await handler.receive_chunk(chunk)
"""

import logging

from langgraph_sdk import get_client
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


class StreamingClient:
    """流式 API 客户端."""

    def __init__(
        self,
        url: str = "http://localhost:2024",
        api_key: str = "",
        assistant_id: str = "research",
    ):
        self.url = url
        self.api_key = api_key
        self.assistant_id = assistant_id
        self._client = get_client(url=url, api_key=api_key)

    async def stream_chat(
        self,
        message: str | list,
        system_prompt: str | None = None,
        thread_id: str | None = None,
        stream_mode: list[str] | None = None,
        **kwargs,
    ):
        """流式聊天主入口，原样返回 chunks."""
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=message))

        stream_mode = stream_mode or ["messages-tuple", "custom"]
        chunks = self._client.runs.stream(
            thread_id=thread_id or "default",
            assistant_id=self.assistant_id,
            input={"messages": messages},
            stream_mode=stream_mode,
            if_not_exists="create",
            **kwargs,
        )
        async for chunk in chunks:
            yield chunk

    async def stream_chat_with_files(
        self,
        message: str,
        files: list[dict] | None = None,
        system_prompt: str | None = None,
        thread_id: str | None = None,
        **kwargs,
    ):
        """流式聊天（支持文件上传）."""
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))

        content_blocks = [{"type": "text", "text": message}]
        if files:
            content_blocks.extend(files)
        messages.append(HumanMessage(content=content_blocks))

        chunks = self._client.runs.stream(
            thread_id=thread_id or "default",
            assistant_id=self.assistant_id,
            input={"messages": messages},
            stream_mode=["messages-tuple", "custom"],
            if_not_exists="create",
            **kwargs,
        )
        async for chunk in chunks:
            yield chunk

    def create_thread(self, thread_id: str) -> str:
        self._client.threads.create(thread_id=thread_id)
        return thread_id

    def get_thread(self, thread_id: str) -> dict:
        return self._client.threads.get(thread_id=thread_id)

    def delete_thread(self, thread_id: str):
        self._client.threads.delete(thread_id=thread_id)
