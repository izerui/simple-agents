"""流式 API 客户端.

使用方式:
    from src.clients import StreamingClient, EventHandlers

    handler = EventHandlers()
    async for chunk in client.stream_chat("你好"):
        await handler.receive_chunk(chunk)

支持的文件格式:
    - 本地文件路径: "path/to/file.pdf" 或 Path("path/to/file.pdf")
    - URL: "https://example.com/file.pdf"
    - 字典格式: {"type": "file", "data": "...", "metadata": {"filename": "..."}}
"""

import base64
import logging
from enum import Enum
from pathlib import Path
from typing import Union

import aiofiles
import aiohttp
from langgraph_sdk import get_client
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

FileType = Union[str, Path, dict]


class EventType(str, Enum):
    """流式事件类型."""

    # 消息事件
    AI_MESSAGE_CHUNK = "ai_message_chunk"  # AI 消息块（流式输出）
    TOOL_MESSAGE = "tool_message"  # 工具消息
    TOOL_CALL_COMPLETE = "tool_call_complete"  # 工具调用完整结果（参数 + 结果）

    # 自定义事件
    CUSTOM = "custom"  # 自定义事件

    # 错误
    ERROR = "error"  # 错误


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
        files: list[FileType] | None = None,
        system_prompt: str | None = None,
        thread_id: str | None = None,
        **kwargs,
    ):
        """流式聊天（支持文件上传）.

        Args:
            message: 用户消息
            files: 文件列表，支持:
                - 本地路径: "path/to/file.pdf" 或 Path("path/to/file.pdf")
                - URL: "https://example.com/file.pdf"
                - 字典格式: {"type": "file", "data": "...", "metadata": {"filename": "..."}}
            system_prompt: 系统提示
            thread_id: 线程 ID
        """
        # 处理文件参数
        processed_files = []
        if files:
            for f in files:
                if isinstance(f, dict):
                    # 已经是字典格式，直接使用
                    processed_files.append(f)
                elif isinstance(f, (str, Path)):
                    # 本地文件路径
                    processed_files.append(await self._load_file(f))
                else:
                    logger.warning(f"Unknown file type: {type(f)}, skipping")

        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))

        content_blocks = [{"type": "text", "text": message}]
        if processed_files:
            content_blocks.extend(processed_files)
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

    async def _load_file(self, file_path: Union[str, Path]) -> dict:
        """加载文件并转为 API 所需格式.

        Args:
            file_path: 文件路径或 URL

        Returns:
            字典格式: {"type": "file", "data": "...", "metadata": {"filename": "..."}}
        """
        path_str = str(file_path)

        # 检查是否是 URL
        if path_str.startswith(("http://", "https://")):
            return await self._download_file(path_str)

        # 本地文件
        return await self._read_local_file(file_path)

    async def _read_local_file(self, file_path: Union[str, Path]) -> dict:
        """读取本地文件."""
        path = Path(file_path)
        filename = path.name

        async with aiofiles.open(path, "rb") as f:
            data = base64.b64encode(await f.read()).decode("utf-8")

        return {
            "type": "file",
            "data": data,
            "metadata": {"filename": filename},
        }

    async def _download_file(self, url: str) -> dict:
        """下载 URL 文件."""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise RuntimeError(f"Failed to download file: {response.status}")

                content = await response.read()
                data = base64.b64encode(content).decode("utf-8")

        # 从 URL 提取文件名
        filename = url.split("/")[-1].split("?")[0] or "downloaded_file"

        return {
            "type": "file",
            "data": data,
            "metadata": {"filename": filename},
        }

    def create_thread(self, thread_id: str) -> str:
        self._client.threads.create(thread_id=thread_id)
        return thread_id

    def get_thread(self, thread_id: str) -> dict:
        return self._client.threads.get(thread_id=thread_id)

    def delete_thread(self, thread_id: str):
        self._client.threads.delete(thread_id=thread_id)
