"""
基于 Docling 的 PDF 到 Markdown 转换器（优化版）

Docling 是一个先进的文档处理库，支持：
- 先进的 PDF 布局分析
- 自动表格识别和转换
- 图片提取和处理
- OCR 支持
- 多种文档格式支持

性能优化：
- 模型只加载一次（避免重复加载）
- 批量处理支持（复用模型实例）
- 默认禁用高成本功能（图片生成、高缩放）
- 支持并发处理（线程控制）

安装依赖：
    pip install docling

更多信息：
    https://github.com/docling-project/docling
"""

import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

from src.utils._library_download import ensure_docling_installed, download_docling_models

# 确保依赖已安装
ensure_docling_installed()

from src.prompts import VLLM_INSTRUCTIONS

# 下载模型
download_docling_models()

logger = logging.getLogger(__name__)

# 导入 docling 相关模块
from docling.document_converter import DocumentConverter, PdfFormatOption, ImageFormatOption, WordFormatOption, \
    PowerpointFormatOption
from docling.datamodel.pipeline_options_vlm_model import ApiVlmOptions, ResponseFormat
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, VlmPipelineOptions, \
    PictureDescriptionApiOptions
from docling_core.types.doc import ImageRefMode, PictureItem
from docling.pipeline.vlm_pipeline import VlmPipeline

logger = logging.getLogger(__name__)

# https://docling-project.github.io/docling/usage/advanced_options/#impose-limits-on-the-document-size
num_threads = 4
os.environ["OMP_NUM_THREADS"] = str(num_threads)


class DoclingConverter:
    """
    Docling 转换器
    """

    def __init__(
            self,
            converter: DocumentConverter,
    ):
        """
        初始化 Docling 转换器

        Args:
            converter: DocumentConverter 转换实例
        """
        self._converter = converter

    def convert(
            self,
            working_dir: str,
            source_file: str,
            output_file: Optional[str] = None,
            debug: bool = True,
    ) -> str:
        """
        转换单个文件（线程安全，支持并发调用）

        Args:
            working_dir: 工作目录（必填），所有相对路径都基于此目录
            source_file: 源文件路径（相对于 working_dir 的相对路径，或 URL）
            output_file: 输出 Markdown 文件路径（相对于 working_dir 的相对路径）
            debug: 是否开启调试模式

        Returns:
            转换后的 Markdown 内容
        """
        try:
            # 将工作目录转换为绝对路径
            working_dir_path = Path(working_dir).resolve()

            # 处理源文件路径
            if source_file.startswith(('http://', 'https://')):
                # URL 不需要转换
                source_path = source_file
            else:
                # 将相对路径转换为绝对路径
                source_path = working_dir_path / source_file
                source_path = source_path.resolve()

            # 检查文件是否存在（仅对本地文件）
            if isinstance(source_path, Path):
                if not source_path.exists():
                    raise FileNotFoundError(f"文档不存在: {source_path}")
                source_file_for_docling = str(source_path)
            else:
                source_file_for_docling = source_path

            # 确定输出路径
            if output_file is None:
                # 如果是 URL，从 URL 中提取文件名
                if source_file.startswith(('http://', 'https://')):
                    from urllib.parse import urlparse
                    parsed = urlparse(source_file)
                    filename = Path(parsed.path).name
                    if not filename.endswith('.pdf'):
                        filename += '.pdf'
                    output_path = working_dir_path / "output" / Path(filename).with_suffix('.md')
                else:
                    output_path = working_dir_path / Path(source_file).with_suffix('.md')
            else:
                # 将输出路径转换为绝对路径
                output_path = working_dir_path / output_file

            output_path = output_path.resolve()

            # 自动创建父目录
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # 确定图片保存目录：images/{output_file的basename}/
            images_dir = working_dir_path / "images" / output_path.stem

            if debug:
                print(f"docling - 工作目录: {working_dir_path}")
                print(f"docling - 开始转换: {source_file_for_docling}")
                print(f"docling - 输出文件: {output_path}")
                print(f"docling - 图片目录: {images_dir}")

            # 执行转换（使用绝对路径）
            print(f"docling - 正在转换文档...")
            convert_start_time = time.time()
            result = self._converter.convert(source_file_for_docling)
            convert_time = time.time() - convert_start_time
            print(f"docling - 文档转换完成，耗时: {convert_time:.2f}秒")

            # 保存为 Markdown 文件
            print(f"docling - 保存 Markdown 文件到: {output_path.parent}")
            # PLACEHOLDER 模式：不生成图片
            result.document.save_as_markdown(
                output_path,
                image_mode=ImageRefMode.PLACEHOLDER
            )

            # 读取生成的 Markdown 内容
            read_start_time = time.time()
            md_text = output_path.read_text(encoding='utf-8')
            read_time = time.time() - read_start_time
            print(f"docling - 读取 Markdown 文件完成，耗时: {read_time:.2f}秒")

            total_time = time.time() - convert_start_time
            print(f"docling - 转换完成，共 {len(md_text)} 字符，总耗时: {total_time:.2f}秒")

            # 及时释放资源
            del result

        except Exception as e:
            print(f"docling - 转换失败: {str(e)}")
            raise

        return md_text


# 快速转换 无图片、无公式
DOCLING_FAST_CONVERTER = DoclingConverter(
    DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=PdfPipelineOptions(
                    do_table_structure=True,
                    do_formula_enrichment=False,
                    generate_picture_images=False,
                    generate_parsed_pages=False,
                )
            )
        }
    ),
)

cus_pipeline_options = PictureDescriptionApiOptions(
    url=os.getenv('VL_MODEL_BASE_URL'),
    headers={
        "Authorization": f"Bearer {os.getenv('VL_MODEL_API_KEY')}"
    },
    concurrency=1,
    params=dict(
        model=os.getenv('VL_MODEL_MODEL_ID'),
        max_tokens=4096,
        temperature=0.2,
    ),
    prompt=VLLM_INSTRUCTIONS,
    timeout=300,
)

# 支持图片提取
DOCLING_IMAGE_CONVERTER = DoclingConverter(
    DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=PdfPipelineOptions(
                    do_table_structure=True,
                    do_formula_enrichment=False,
                    generate_picture_images=True,
                    do_picture_description=True,
                    enable_remote_services=True,
                    picture_description_options=cus_pipeline_options,
                    images_scale=2.0,
                    generate_parsed_pages=False,
                )
            ),
            InputFormat.DOCX: WordFormatOption(
                pipeline_options=PdfPipelineOptions(
                    do_table_structure=True,
                    do_formula_enrichment=False,
                    generate_picture_images=True,
                    do_picture_description=True,
                    enable_remote_services=True,
                    picture_description_options=cus_pipeline_options,
                    images_scale=2.0,
                    generate_parsed_pages=False,
                )
            ),
        }
    ),
)

llm_pipeline_options = VlmPipelineOptions(
    enable_remote_services=True,
    vlm_options=ApiVlmOptions(
        url=os.getenv('VL_MODEL_BASE_URL'),
        headers={
            "Authorization": f"Bearer {os.getenv('VL_MODEL_API_KEY')}"
        },
        concurrency=1,
        params=dict(
            model=os.getenv('VL_MODEL_MODEL_ID'),
            max_tokens=4096,
            temperature=0.0,
        ),
        prompt=VLLM_INSTRUCTIONS,
        response_format=ResponseFormat.MARKDOWN,
        timeout=300,
    )
)

# 同时支持图片提取和公式识别
DOCLING_LLM_CONVERTER = DoclingConverter(
    DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_cls=VlmPipeline,
                pipeline_options=llm_pipeline_options,
            ),
            InputFormat.IMAGE: ImageFormatOption(
                pipeline_cls=VlmPipeline,
                pipeline_options=llm_pipeline_options,
            ),
            InputFormat.DOCX: WordFormatOption(
                pipeline_cls=VlmPipeline,
                pipeline_options=llm_pipeline_options,
            ),
            InputFormat.PPTX: PowerpointFormatOption(
                pipeline_cls=VlmPipeline,
                pipeline_options=llm_pipeline_options,
            ),
        },
    ),
)
