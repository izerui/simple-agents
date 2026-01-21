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

from docling.datamodel.pipeline_options_vlm_model import ApiVlmOptions, ResponseFormat
from docling.pipeline.vlm_pipeline import VlmPipeline
from dotenv import load_dotenv

from src.utils._docling_download import ensure_docling_installed, download_docling_models

logger = logging.getLogger(__name__)

# 加载环境变量并添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
load_dotenv(dotenv_path=project_root / '.env')

# 确保依赖已安装
ensure_docling_installed()

# 下载模型
download_docling_models()

# 导入 docling 相关模块
from docling.document_converter import DocumentConverter, PdfFormatOption, ImageFormatOption, WordFormatOption, \
    PowerpointFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, VlmPipelineOptions, \
    PictureDescriptionApiOptions
from docling_core.types.doc import ImageRefMode, PictureItem

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
            generate_picture_images: bool = False
    ):
        """
        初始化 Docling 转换器

        Args:
            converter: DocumentConverter 转换实例
        """
        self._converter = converter
        self.generate_picture_images = generate_picture_images

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
                print(f"docling - 生成图片: {'启用' if self.generate_picture_images else '禁用'}")
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
            if self.generate_picture_images:
                # 创建图片目录
                # images_dir.mkdir(parents=True, exist_ok=True)

                # REFERENCED 模式：图片保存为独立文件
                result.document.save_as_markdown(
                    output_path,
                    image_mode=ImageRefMode.REFERENCED,
                    artifacts_dir=images_dir
                )
            else:
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

            # 将图片链接从绝对路径替换为相对于工作目录的相对路径
            # 例如：/absolute/path/to/project/images/doc1/image.png -> images/doc1/image.png
            if self.generate_picture_images:
                import re
                working_dir_str = str(working_dir_path)
                # 移除工作目录前缀（确保不匹配部分路径）
                # 使用正向预查确保只匹配完整的工作目录路径
                md_text = re.sub(
                    rf'^{re.escape(working_dir_str)}/',
                    '',
                    md_text,
                    flags=re.MULTILINE
                )
                # 替换 Markdown 图片链接中的绝对路径
                # 格式：![alt](/absolute/path/to/project/images/...)
                md_text = re.sub(
                    rf'!\[([^\]]*)\]\({re.escape(working_dir_str)}/([^\)]+)\)',
                    r'![\1](\2)',
                    md_text
                )

                # 收集图片描述信息
                # 收集所有图片描述（按出现顺序）
                description_list = []
                for element, _level in result.document.iterate_items():
                    if isinstance(element, PictureItem):
                        print(f"图片 {element.self_ref}")

                        _pic: PictureItem = element
                        # 获取描述文本
                        description_text = "无描述"
                        if hasattr(_pic.meta, 'description') and _pic.meta.description:
                            description_text = _pic.meta.description.text
                        print(f"描述: {description_text}")

                        # 将描述添加到列表中（保持顺序）
                        description_list.append(description_text)
                        print("-" * 80)

                # 将描述按顺序插入到对应的图片位置后面
                # 匹配以 ![Image](images/ 开头的行
                lines = md_text.split('\n')
                desc_index = 0
                new_lines = []
                for line in lines:
                    new_lines.append(line)
                    # 如果这行是以 ![Image](images/ 开头，就插入描述
                    if line.strip().startswith('![Image](images/'):
                        if desc_index < len(description_list):
                            description = description_list[desc_index]
                            # 插入图片说明
                            new_lines.append(f"\n**图片说明：**")
                            # 将描述按行分割，每行都添加 >
                            for desc_line in description.split('\n'):
                                new_lines.append(f"> {desc_line}")
                            desc_index += 1
                            print(f"已在第 {len(new_lines)} 行插入第 {desc_index} 个图片的描述")

                # 重新组合文本
                md_text = '\n'.join(new_lines)

                # 写回文件
                output_path.write_text(md_text, encoding='utf-8')

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
    generate_picture_images=False
)

cus_pipeline_options = PictureDescriptionApiOptions(
    url=os.getenv('VL_MODEL_BASE_URL'),
    headers={
        "Authorization": f"Bearer {os.getenv('VL_MODEL_API_KEY')}"
    },
    concurrency=4,
    params=dict(
        model=os.getenv('VL_MODEL_MODEL_ID'),
        max_tokens=1024,
        temperature=0.2,
    ),
    prompt="""请详细识别并描述图片中的所有内容，包括文字、图表、表格、图像含义等。不要遗漏任何信息。""",
    timeout=90,
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
    generate_picture_images=True
)

llm_pipeline_options = VlmPipelineOptions(
    enable_remote_services=True,
    vlm_options=ApiVlmOptions(
        url=os.getenv('VL_MODEL_BASE_URL'),
        headers={
            "Authorization": f"Bearer {os.getenv('VL_MODEL_API_KEY')}"
        },
        concurrency=4,
        params=dict(
            model=os.getenv('VL_MODEL_MODEL_ID'),
            max_tokens=8192,
            temperature=0.0,
        ),
        prompt="Convert this page to markdown.",
        response_format=ResponseFormat.MARKDOWN,
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
    generate_picture_images=False
)

# --- 使用示例 ---

if __name__ == "__main__":
    import sys

    # 替换为你的 PDF 文件路径
    working_dir = "/Users/liuyuhua/PycharmProjects/simple-agents/files"
    pdf_file = "朝天府.pdf"
    output_file = "朝天府.md"

    try:
        # 示例 3: 启用高级功能（较慢）
        print("\n" + "=" * 60)
        print("示例 3: 启用图片")
        print("=" * 60)
        result3 = DOCLING_IMAGE_CONVERTER.convert(
            working_dir=working_dir,
            source_file=pdf_file,
            output_file=output_file,
        )
        print(f"\n转换结果长度: {len(result3)} 字符")

        # 示例 4: 调试模式
        # print("\n" + "=" * 60)
        # print("示例 4: 调试模式")
        # print("=" * 60)
        # result4 = convert_pdf_to_markdown(
        #     pdf_file,
        #     output_file=output_file,
        #     debug=True,
        # )

    except FileNotFoundError as e:
        print(f"错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"转换失败: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
