import asyncio
import base64
import logging
from pathlib import Path
from typing import Any, Callable, Awaitable

from langchain.agents.middleware.types import AgentMiddleware, StateT
from langchain_core.messages import ToolMessage, HumanMessage
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
    """提取消息中的附件的中间件"""

    def __init__(self, backend_factory: BACKEND_TYPES | None = None):
        # Use provided backend factory
        self.backend_factory = backend_factory
        self.attachments = []
        logger.info("Initialized AttachmentExtractMiddleware")

    async def _get_backend(self, runtime: ToolRuntime) -> BackendProtocol:
        """Get the resolved backend instance from backend or factory.

        Args:
            runtime: The tool runtime context.

        Returns:
            Resolved backend instance.
        """
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
        return {"aaa": "bbb"}

    async def awrap_tool_call(
            self,
            request: ToolCallRequest,
            handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        backend: AsyncFilesystemBackend = await self._get_backend(request.runtime)
        # 处理附件
        messages = request.state['messages']
        # 获取数组最后一个 HumanMessage，不存在则返回空列表
        human_messages: list[HumanMessage] = []
        for msg in reversed(messages):
            if msg.type == 'human':
                human_messages = [msg]
                break

        # 直接从 HumanMessage 的 content 中提取 files
        try:
            files = []
            for msg in human_messages:
                if msg.content and isinstance(msg.content, list):
                    for block in msg.content:
                        if isinstance(block, dict):
                            block_type = block.get("type")
                            # {"type": "file", "metadata": {'filename': 'myfile.pdf'}, "data": "base64_string", "mimeType": "application/pdf", "cache_control": {'ttl': '5m', 'type': 'ephemeral'}}
                            if block_type == "file":
                                filename = block['metadata']['filename']
                                files.append((filename, base64.b64decode(block['data'])))
                            # {"type": "image", "metadata": {"name": "1.jpg"}, "mime_type": "image/jpeg", "data": "base64_string"}
                            elif block_type == "image":
                                filename = block['metadata']['name']
                                files.append((filename, base64.b64decode(block['data'])))

            if len(files) <= 0:
                # 调用原始处理函数
                return await handler(request)

            # 获取已上传的文件集合，避免重复上传
            uploaded_files = request.state.setdefault('uploaded_files', set())

            # 过滤掉已上传的文件
            files_to_upload = []
            for filename, content in files:
                if filename not in uploaded_files:
                    files_to_upload.append((filename, content))
                    uploaded_files.add(filename)
                else:
                    logger.info(f"文件 {filename} 已上传，跳过")

            if len(files_to_upload) > 0:
                logger.info(
                    f"开始上传 {len(files_to_upload)} 个文件: {[Path(filename).name for filename, _ in files_to_upload]}")
                uploads: list[FileUploadResponse] = await backend.aupload_files(files_to_upload)
                logger.info(f"文件上传完成，共 {len(uploads)} 个上传任务")

                # 上传成功后立即开始并行转换
                # 筛选出成功上传的文件
                successful_uploads = [u for u in uploads if u.error is None]

                if len(successful_uploads) > 0:
                    logger.info(f"开始并行转换 {len(successful_uploads)} 个文件")

                    # 创建转换任务
                    convert_tasks = []
                    for upload in successful_uploads:
                        file_path = Path(await backend.aabs_path(upload.path))
                        file_ext = file_path.suffix.lower()

                        async def convert_file(file_path: Path, file_ext: str):
                            try:
                                # 遍历所有转换器，找到支持该文件类型的转换器
                                for converter in converters:
                                    if converter.support(file_ext):
                                        output_file = file_path.with_suffix('.md')
                                        # 使用 asyncio.to_thread 在线程池中执行同步的转换方法，避免阻塞事件循环
                                        await asyncio.to_thread(converter.convert, str(file_path), str(output_file))
                                        logger.info(f"转换成功: {file_path.name} -> {output_file.name}")
                                        # 转换为虚拟路径
                                        virt_file = await backend.ato_virt_path(str(file_path))
                                        virt_output = await backend.ato_virt_path(str(output_file))
                                        return {"file": virt_file, "output": virt_output, "status": "success"}
                                
                                # 所有转换器都不支持该文件类型
                                logger.info(f"跳过不支持的文件类型: {file_path.name}")
                                virt_file = await backend.ato_virt_path(str(file_path))
                                return {"file": virt_file, "status": "skipped",
                                        "reason": f"不支持的文件类型: {file_ext}"}
                            except Exception as e:
                                logger.error(f"文件转换失败 {file_path.name}: {e}")
                                # 转换为虚拟路径
                                virt_file = await backend.ato_virt_path(str(file_path))
                                return {"file": virt_file, "status": "failed", "error": str(e)}

                        convert_tasks.append(convert_file(file_path, file_ext))

                    # 并行执行所有转换任务
                    if convert_tasks:
                        convert_results = await asyncio.gather(*convert_tasks, return_exceptions=True)

                        # 统计转换结果
                        success_count = sum(
                            1 for r in convert_results if isinstance(r, dict) and r.get("status") == "success")
                        failed_count = sum(
                            1 for r in convert_results if isinstance(r, dict) and r.get("status") == "failed")
                        skipped_count = sum(
                            1 for r in convert_results if isinstance(r, dict) and r.get("status") == "skipped")

                        logger.info(f"转换完成: 成功 {success_count}, 失败 {failed_count}, 跳过 {skipped_count}")

                        # 将转换结果存入 state，供后续使用
                        conversion_results = [r for r in convert_results if isinstance(r, dict)]
                        request.state.setdefault('conversion_results', []).extend(conversion_results)
            else:
                logger.info("所有文件都已上传，无需重复上传")

            request.state['uploaded'] = True
        except asyncio.TimeoutError as e:
            logger.error(f"文件转换超时: {e}")
            raise
        except Exception as e:
            logger.error(f"上传或转换文件时发生错误: {e}", exc_info=True)
            raise

        # 调用原始处理函数
        return await handler(request)

    def get_attachments(self) -> list:
        """获取提取的附件"""
        return self.attachments
