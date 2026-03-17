import asyncio
import base64
import logging
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, unquote

import aiofiles.os
import aiohttp

from langchain.agents.middleware.types import AgentMiddleware, StateT
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_config
from langgraph.prebuilt.tool_node import ToolRuntime
from langgraph.runtime import Runtime
from langgraph.typing import ContextT

from deepagents.backends import FilesystemBackend
from deepagents.backends.protocol import BACKEND_TYPES, BackendProtocol, FileUploadResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def copytree_hardlink(src, dst):
    """跨平台硬链接复制"""
    # 如果目标已存在，跳过
    if os.path.exists(dst):
        logger.info(f"⏭️ skills 已存在，跳过: {dst}")
        return

    system = platform.system()
    success = False
    if system == "Linux":
        # Linux 使用 cp -al
        try:
            subprocess.run(['cp', '-al', str(src), str(dst)], check=True)
            success = True
            logger.info(f"✅ 使用硬链接复制 skills: {src} -> {dst}")
        except Exception as e:
            logger.warning(f"⚠️ linux 创建 skills 硬链接 失败: {e}")
    else:
        # 其他系统使用普通复制
        shutil.copytree(src, dst, dirs_exist_ok=True)
        success = True
        logger.info(f"✅ 使用普通复制 skills: {src} -> {dst}")

    # 如果都失败，使用普通复制
    if not success:
        logger.warning("⚠️ 硬链接方法失败，使用普通复制 skills")
        shutil.copytree(src, dst, dirs_exist_ok=True)


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
                        # {"type": "file_url", "url": "https://example.com/myfile.pdf", "metadata": {"filename": "myfile.pdf"}, "mimeType": "application/pdf"}
                        elif block_type == "file_url":
                            extracted_attachments.append({
                                'type': 'file_url',
                                'filename': block.get('metadata', {}).get('filename'),
                                'url': block.get('url', ''),
                                'mime_type': block.get('mimeType')
                            })
                # 过滤掉文件和图像类型的块
                filtered_content = [
                    block for block in msg.content
                    if not (isinstance(block, dict) and block.get("type") in ("file", "image", "file_url"))
                ]

                # 在内容中添加上传文件的提示信息
                if extracted_attachments:
                    file_names = [att['filename'] for att in extracted_attachments]
                    file_info = "\n\n文件列表:\n" + "\n    ".join(file_names)
                    # 将文件信息以字典格式添加到 filtered_content 末尾
                    filtered_content.append({"type": "text", "text": file_info})

                # 创建新的 HumanMessage，只包含纯文本（兼容通义千问等模型）
                new_msg = msg.copy(update={"content": filtered_content})
                updated_messages.append(new_msg)
            else:
                # 非人类消息或非列表内容，保持原样
                updated_messages.append(msg)

        config: RunnableConfig = get_config()
        #  获取后端实例
        backend: FilesystemBackend = self._get_backend(config)

        # 如果有提取的附件，上传到沙箱目录
        if extracted_attachments:
            await self.upload_files(backend, extracted_attachments)

        # 检查并复制 skills 目录到沙箱
        await asyncio.to_thread(self._ensure_skills_in_sandbox, backend)

        # 更新消息
        return {'messages': updated_messages}

    async def upload_files(self, backend: FilesystemBackend, extracted_attachments: list[dict]):
        # 准备上传的文件列表
        files_to_upload = []
        for attachment in extracted_attachments:
            if attachment['type'] == 'file_url':
                download_result = await self._download_attachment_from_url(attachment)
                if download_result is None:
                    continue
                filename, data = download_result
            else:
                filename = attachment['filename']
                data = self._decode_attachment_base64(attachment)
                if data is None:
                    logger.warning(f"跳过附件上传，base64 解码失败: {filename}")
                    continue
            files_to_upload.append((filename, data))

        # 上传前删除 backend 中已有的同名文件，以及同 stem 不同后缀文件
        if files_to_upload:
            await self._remove_conflicting_backend_files(backend, files_to_upload)

        # 上传文件
        if files_to_upload:
            logger.info(
                f"开始上传 {len(files_to_upload)} 个文件: "
                f"{[Path(filename).name for filename, _ in files_to_upload]}"
            )
            uploads: list[FileUploadResponse] = await backend.aupload_files(files_to_upload)
            logger.info(f"文件上传完成，共 {len(uploads)} 个上传任务")

    async def _remove_conflicting_backend_files(self, backend: FilesystemBackend, files_to_upload: list[tuple[str, bytes]]):
        target_names = {Path(filename).name for filename, _ in files_to_upload}
        target_stems = {Path(filename).stem for filename, _ in files_to_upload}
        removed_files: list[str] = []

        existing_paths = await asyncio.to_thread(lambda: list(backend.cwd.iterdir()))
        for existing_path in existing_paths:
            if not await asyncio.to_thread(existing_path.is_file):
                continue

            existing_name = existing_path.name
            existing_stem = existing_path.stem
            if existing_name in target_names or existing_stem in target_stems:
                try:
                    resolved_path = await asyncio.to_thread(backend._resolve_path, existing_name)
                    await aiofiles.os.remove(resolved_path)
                    removed_files.append(existing_name)
                except FileNotFoundError:
                    continue
                except OSError as e:
                    logger.warning(f"删除已有冲突文件失败: {existing_path}, error={e}")

        if removed_files:
            logger.info(f"上传前删除已有冲突文件: {removed_files}")

    def _decode_attachment_base64(self, attachment: dict) -> bytes | None:
        raw_data = attachment.get('data', '')
        if not isinstance(raw_data, str) or not raw_data:
            return None

        base64_data = raw_data.strip()
        if ',' in base64_data and ';base64' in base64_data:
            base64_data = base64_data.split(',', 1)[1]

        missing_padding = len(base64_data) % 4
        if missing_padding:
            base64_data += '=' * (4 - missing_padding)

        try:
            return base64.b64decode(base64_data)
        except Exception as e:
            filename = attachment.get('filename', 'unknown')
            logger.warning(f"附件 base64 解码失败: {filename}, error={e}")
            return None

    async def _download_attachment_from_url(self, attachment: dict) -> tuple[str, bytes] | None:
        url = attachment.get('url', '')
        if not isinstance(url, str) or not url:
            logger.warning("跳过 URL 附件：url 为空或非法")
            return None

        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            logger.warning(f"跳过 URL 附件：不支持的协议 {url}")
            return None

        timeout = aiohttp.ClientTimeout(total=30)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.warning(f"URL 附件下载失败: {url}, status={response.status}")
                        return None
                    data = await response.read()
        except Exception as e:
            logger.warning(f"URL 附件下载异常: {url}, error={e}")
            return None

        if not data:
            logger.warning(f"URL 附件下载为空内容: {url}")
            return None

        filename = self._resolve_download_filename(attachment, parsed.path)
        return filename, data

    def _resolve_download_filename(self, attachment: dict, url_path: str) -> str:
        metadata_filename = attachment.get('filename')
        if isinstance(metadata_filename, str) and metadata_filename.strip():
            return Path(metadata_filename).name

        resolved_name = Path(unquote(url_path)).name
        if resolved_name:
            return resolved_name

        return 'downloaded_file'

    def _ensure_skills_in_sandbox(self, backend: FilesystemBackend):
        """确保 skills 目录存在于沙箱中

        检查沙箱中的 /skills 目录是否存在，如果不存在则从 src/skills 复制到沙箱
        """
        # 获取项目根目录和源 skills 路径
        project_root = Path(__file__).parent.parent.parent
        src_skills_path = project_root / 'src' / 'skills'
        sandbox_skills_path = backend.cwd / 'skills'

        # 检查源 skills 目录是否存在
        if not src_skills_path.exists():
            logger.warning(f"源 skills 目录不存在: {src_skills_path}")
            return

        # 检查沙箱 skills 目录是否存在
        if not sandbox_skills_path.exists():
            # 复制整个 src/skills 目录到沙箱内
            logger.info(f"复制 skills 目录到沙箱: {src_skills_path} -> {sandbox_skills_path}")
            copytree_hardlink(str(src_skills_path), str(sandbox_skills_path))
