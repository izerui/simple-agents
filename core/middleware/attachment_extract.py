import asyncio
import base64
import logging
import os.path
from pathlib import Path
from typing import Any, Callable, Awaitable

from langchain.agents.middleware.types import AgentMiddleware, StateT, ModelCallResult, ModelResponse, ModelRequest
from langchain_core.messages import ToolMessage, HumanMessage
from langgraph.prebuilt.tool_node import ToolCallRequest, ToolRuntime
from langgraph.runtime import Runtime
from langgraph.types import Command
from langgraph.typing import ContextT

from deepagents.backends import StateBackend
from deepagents.backends.filesystem_async import AsyncFilesystemBackend
from deepagents.backends.protocol import BACKEND_TYPES, BackendProtocol, FileUploadResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AttachmentExtractMiddleware(AgentMiddleware):
    """提取消息中的附件的中间件"""

    def __init__(self, backend_factory: BACKEND_TYPES | None = None):
        # Use provided backend or default to StateBackend factory
        self.backend_factory = backend_factory
        logger.info("Initialized AttachmentExtractMiddleware")


    async def _get_backend(self, runtime: ToolRuntime) -> BackendProtocol:
        """Get the resolved backend instance from backend or factory.

        Args:
            runtime: The tool runtime context.

        Returns:
            Resolved backend instance.
        """
        if callable(self.backend_factory):
            return self.backend_factory(runtime)
        return self.backend_factory

    async def abefore_model(self, state: StateT, runtime: Runtime[ContextT]) -> dict[str, Any] | None:
        return {"aaa": "bbb"}

    async def awrap_tool_call(
            self,
            request: ToolCallRequest,
            handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        backend: AsyncFilesystemBackend = await self._get_backend(request.runtime)
        thread_id = backend.get_thread_id()
        # 处理附件
        messages = request.state['messages']
        # 获取这个list 里面 类型是 HumanMessage 的 对象,通过推导式
        human_messages: list[HumanMessage] = [msg for msg in messages if msg.type == 'human']
        # {"type": "file", "metadata": {'filename': 'myfile.pdf'}, "data": "base64_string", "mimeType": "application/pdf", "cache_control": {'ttl': '5m', 'type': 'ephemeral'}}
        attachments = []
        # {"type": "image", "metadata": {"name": "1.jpg"}, "mime_type": "image/jpeg", "data": "base64_string"}
        images = []
        for msg in human_messages:
            if msg.content:
                for block in msg.content:
                    if isinstance(block, dict):
                        if block.get("type") == "file":
                            attachments.append(block)
                        elif block.get("type") == "image":
                            images.append(block)

        # 将 attachments 和 images 按原有文件名写入到 backend 的 /home目录下
        try:
            files = [
                (item['metadata']['filename'], base64.b64decode(item['data']))
                for item in attachments
            ]
            files.extend([
                (item['metadata']['name'], base64.b64decode(item['data']))
                for item in images
            ])

            if len(files) > 0:
                logger.info(f"开始上传 {len(files)} 个文件")
                uploads: list[FileUploadResponse] = await backend.aupload_files(files)
                logger.info(f"文件上传完成，共 {len(uploads)} 个上传任务")
                request.state['uploaded'] = True
        except asyncio.TimeoutError as e:
            logger.error(f"文件转换超时: {e}")
            raise
        except Exception as e:
            logger.error(f"上传或转换文件时发生错误: {e}", exc_info=True)
            raise

        # 调用原始处理函数
        return await handler(request)

    def get_attachments(self):
        """获取提取的附件"""
        return self.attachments
