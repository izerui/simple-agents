import asyncio
import base64
import logging
from pathlib import Path
from typing import Any, Callable, Awaitable

from langchain.agents.middleware.types import AgentMiddleware, StateT
from langchain_core.messages import ToolMessage, HumanMessage
from langgraph.types import Overwrite
from langgraph.prebuilt.tool_node import ToolCallRequest, ToolRuntime
from langgraph.runtime import Runtime
from langgraph.types import Command
from langgraph.typing import ContextT

from core.converters.base import BaseConverter
from core.converters.docx import DOCX2Markdown
from core.converters.pdf import PDF2Markdown
from deepagents.backends.filesystem_async import AsyncFilesystemBackend
from deepagents.backends.protocol import BACKEND_TYPES, BackendProtocol, FileUploadResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 注册转换器
converters: list[BaseConverter] = [
    PDF2Markdown(),
    DOCX2Markdown()
]


class AttachmentExtractMiddleware(AgentMiddleware):
    """提取消息中的附件的中间件
    
    工作流程：
    1. abefore_model: 从 HumanMessage 中提取 type="file" 和 type="image" 的附件到 state，
       并将消息内容转换为纯文本（兼容通义千问等不支持列表格式的模型）
    2. awrap_tool_call: 从 state 中获取附件，上传到后端，处理完成后清理 state
    """

    def __init__(self, backend_factory: BACKEND_TYPES | None = None):
        self.backend_factory = backend_factory
        logger.info("Initialized AttachmentExtractMiddleware")
    
    async def _get_backend(self, runtime: ToolRuntime) -> BackendProtocol:
        """从后端工厂获取后端实例"""
        if self.backend_factory is None:
            raise ValueError("backend_factory must be provided")
        if callable(self.backend_factory):
            backend = self.backend_factory(runtime)
        else:
            backend = self.backend_factory
        if backend is None:
            raise ValueError("Backend factory returned None")
        return backend
    
    def _extract_text_from_content(self, content) -> str:
        """从 content 中提取纯文本
        
        Args:
            content: 可以是字符串或列表格式的内容
            
        Returns:
            纯文本字符串
        """
        if isinstance(content, str):
            return content
        
        if isinstance(content, list):
            text_blocks = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_blocks.append(block.get("text", ""))
            return "\n".join(text_blocks)
        
        return ""
    
    async def abefore_model(self, state: StateT, runtime: Runtime[ContextT]) -> dict[str, Any] | None:
        """在模型调用前处理：提取附件到 state，清理消息内容
        
        这个函数：
        1. 从 HumanMessage 的 content 中提取 type="file" 和 type="image" 的块
        2. 将提取的附件存储到 state['pending_attachments']
        3. 将消息内容转换为纯文本，移除所有附件块
        4. 确保消息格式兼容通义千问等模型（纯文本字符串）
        
        Args:
            state: 当前状态
            runtime: 运行时上下文
            
        Returns:
            更新的 state，包含清理后的消息和提取的附件
        """
        messages = state.get('messages', [])
        updated_messages = []
        extracted_attachments = []
        
        # 遍历消息，处理 HumanMessage
        for msg in messages:
            if msg.type == 'human' and msg.content and isinstance(msg.content, list):
                # 提取文件和图片附件
                for block in msg.content:
                    if isinstance(block, dict):
                        block_type = block.get("type")
                        # {"type": "file", "metadata": {'filename': 'myfile.pdf'}, "data": "base64_string", "mimeType": "application/pdf"}
                        if block_type == "file":
                            filename = block['metadata'].get('filename', 'unknown')
                            extracted_attachments.append({
                                'type': 'file',
                                'filename': filename,
                                'data': block.get('data', ''),
                                'mime_type': block.get('mimeType')
                            })
                        # {"type": "image", "metadata": {"name": "1.jpg"}, "mime_type": "image/jpeg", "data": "base64_string"}
                        elif block_type == "image":
                            filename = block['metadata'].get('name', 'unknown')
                            extracted_attachments.append({
                                'type': 'image',
                                'filename': filename,
                                'data': block.get('data', ''),
                                'mime_type': block.get('mime_type')
                            })
                # 过滤掉文件和图像类型的块
                filtered_content = [
                    block for block in msg.content
                    if not (isinstance(block, dict) and block.get("type") in ("file", "image"))
                ]

                # 创建新的 HumanMessage，只包含纯文本（兼容通义千问等模型）
                new_msg = msg.copy(update={"content": filtered_content})
                updated_messages.append(new_msg)
            else:
                # 非人类消息或非列表内容，保持原样
                updated_messages.append(msg)
        
        # 如果有提取的附件，更新 state
        if extracted_attachments:
            logger.info(f"提取了 {len(extracted_attachments)} 个附件到 state: {[a['filename'] for a in extracted_attachments]}")
            return {
                'messages': updated_messages,
                'pending_attachments': extracted_attachments
            }
        
        # 没有附件，只更新消息
        return {'messages': updated_messages}
    
    async def awrap_tool_call(
            self,
            request: ToolCallRequest,
            handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        """处理工具调用：从 state 上传附件，完成后清理
        
        这个函数：
        1. 从 state['pending_attachments'] 获取之前提取的附件
        2. 解码 base64 数据并上传到后端
        3. 避免重复上传（通过 state['uploaded_files'] 集合）
        4. 处理完成后清理 state['pending_attachments']
        
        Args:
            request: 工具调用请求
            handler: 原始处理函数
            
        Returns:
            工具消息或命令
        """
        # 检查是否有待处理的附件
        pending_attachments = request.state.get('pending_attachments', [])
        
        if not pending_attachments:
            # 没有附件，直接调用原始处理函数
            return await handler(request)
        
        try:
            backend: AsyncFilesystemBackend = await self._get_backend(request.runtime)
            
            # 获取已上传的文件集合，避免重复上传
            uploaded_files = request.state.setdefault('uploaded_files', set())
            
            # 准备上传的文件列表
            files_to_upload = []
            for attachment in pending_attachments:
                filename = attachment['filename']
                if filename not in uploaded_files:
                    # 解码 base64 数据
                    data = base64.b64decode(attachment['data'])
                    files_to_upload.append((filename, data))
                    uploaded_files.add(filename)
                else:
                    logger.info(f"文件 {filename} 已上传，跳过")
            
            # 上传文件
            if files_to_upload:
                logger.info(
                    f"开始上传 {len(files_to_upload)} 个文件: "
                    f"{[Path(filename).name for filename, _ in files_to_upload]}"
                )
                uploads: list[FileUploadResponse] = await backend.aupload_files(files_to_upload)
                logger.info(f"文件上传完成，共 {len(uploads)} 个上传任务")
            
            # 标记已上传
            request.state['uploaded'] = True
            
            # 清理待处理的附件（处理完成后移除）
            request.state.pop('pending_attachments', None)
            logger.info("附件处理完成，已从 state 中清理 pending_attachments")
        
        except Exception as e:
            logger.error(f"处理附件时发生错误: {e}", exc_info=True)
            # 发生错误时也清理附件，避免卡住
            request.state.pop('pending_attachments', None)
            raise
        
        # 调用原始处理函数
        return await handler(request)