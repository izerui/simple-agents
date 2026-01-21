import asyncio
import base64
import logging
from pathlib import Path
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware, StateT
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_config
from langgraph.prebuilt.tool_node import ToolRuntime
from langgraph.runtime import Runtime
from langgraph.typing import ContextT

from deepagents.backends import FilesystemBackend
from src.utils._word_to_pdf import word_to_pdf
from deepagents.backends.protocol import BACKEND_TYPES, BackendProtocol, FileUploadResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



def _word_to_pdf_base64(filename: str, data: str) -> str:
    # 解码base64数据并保存为临时文件
    word_data = base64.b64decode(data)
    import tempfile
    import os

    # 创建临时目录和文件
    temp_dir = tempfile.mkdtemp()
    temp_word_path = os.path.join(temp_dir, filename)

    with open(temp_word_path, 'wb') as f:
        f.write(word_data)

    # 转换为PDF
    try:
        pdf_data = word_to_pdf(temp_word_path)
        # 更新数据为PDF的base64编码
        data = base64.b64encode(pdf_data).decode('utf-8')
        logger.info(f"Word文件已转换为PDF: {filename}")
        return data
    except Exception as e:
        logger.error(f"Word文件转换为PDF失败: {e}")
        return None
    finally:
        # 清理临时文件
        os.remove(temp_word_path)
        os.rmdir(temp_dir)


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

    def _get_backend(self, runtime: ToolRuntime | RunnableConfig | dict) -> BackendProtocol:
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
                            # 判断是否是Word文件
                            mime_type = block.get('mimeType', '')
                            data = block.get('data', '')
                            file_extension = Path(filename).suffix.lower()

                            # Word文件的MIME类型或扩展名检查
                            is_word_file = (
                                mime_type in [
                                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
                                    'application/msword'  # .doc
                                ]
                                or file_extension in ['.docx', '.doc']
                            )

                            if is_word_file:
                                _data = await asyncio.to_thread(_word_to_pdf_base64, filename, data)
                                if _data:
                                    data = _data
                                    # 更新文件名和MIME类型
                                    filename = Path(filename).stem + '.pdf'
                                    mime_type = 'application/pdf'

                            extracted_attachments.append({
                                'type': 'file',
                                'filename': filename,
                                'data': data,
                                'mime_type': mime_type
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

                # 在内容中添加上传文件的提示信息
                if extracted_attachments:
                    file_names = [att['filename'] for att in extracted_attachments]
                    file_info = "\n\n上传文件清单:\n" + "\n    ".join(file_names)
                    # 将文件信息以字典格式添加到 filtered_content 末尾
                    filtered_content.append({"type": "text", "text": file_info})

                # 创建新的 HumanMessage，只包含纯文本（兼容通义千问等模型）
                new_msg = msg.copy(update={"content": filtered_content})
                updated_messages.append(new_msg)
            else:
                # 非人类消息或非列表内容，保持原样
                updated_messages.append(msg)

        # 如果有提取的附件，上传到沙箱目录
        if extracted_attachments:
            config: RunnableConfig = get_config()
            #  获取后端实例
            backend: FilesystemBackend = self._get_backend(config)
            await self.upload_files(backend, extracted_attachments)
            pass

        # 更新消息
        return {'messages': updated_messages}

    async def upload_files(self, backend: FilesystemBackend, extracted_attachments: list[dict]):
        # 准备上传的文件列表
        files_to_upload = []
        for attachment in extracted_attachments:
            filename = attachment['filename']
            # 解码 base64 数据
            data = base64.b64decode(attachment['data'])
            files_to_upload.append((filename, data))

        # 上传文件
        if files_to_upload:
            logger.info(
                f"开始上传 {len(files_to_upload)} 个文件: "
                f"{[Path(filename).name for filename, _ in files_to_upload]}"
            )
            uploads: list[FileUploadResponse] = await backend.aupload_files(files_to_upload)
            logger.info(f"文件上传完成，共 {len(uploads)} 个上传任务")
