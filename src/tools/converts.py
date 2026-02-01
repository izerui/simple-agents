"""
转换成 Markdown 工具
"""
import subprocess
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from src.utils._docling import DOCLING_FAST_CONVERTER, DOCLING_IMAGE_CONVERTER, DOCLING_LLM_CONVERTER
from src.utils._word_to_pdf import word_to_pdf
from src.utils.util import get_backend_per_thread


@tool(parse_docstring=True)
def convert_to_markdown(
        source_path: str,
        generate_picture_images: bool = False,
        do_formula_enrichment: bool = False,
) -> dict[str, Any]:
    """将 DOCX、XLSX、PPTX、PNG、 JPG、 JPEG、 GIF、 BMP、 AsciiDoc 文件转换为 Markdown 格式以便研究。

    该工具将文档转换为 Markdown 格式。根据用户的问题内容来决定是否启用特殊功能：
    
    启用图片提取的时机：当用户问题涉及图片、图表、截图、图形、插图、示意图、流程图、截图中的文字、界面展示等视觉内容时，应将 generate_picture_images 设为 True
    
    启用公式识别的时机：当用户问题涉及数学公式、方程、不等式、符号、微积分、数学表达式、化学方程式、物理公式等内容时，应将 do_formula_enrichment 设为 True

    Args:
        source_path: 要转换的文件路径
        generate_picture_images: 是否识别并提取图片（根据用户问题是否涉及视觉内容决定）
        do_formula_enrichment: 是否识别公式（根据用户问题是否涉及数学公式决定）

    Returns:
        包含以下内容的字典：
        - success: 转换是否成功
        - source_path: 源文件的路径
        - output_file: 生成的 Markdown 文件路径
        - error: 转换失败时的错误信息

    Notes:
        - 图片提取到 {output_file} 同目录下的 'images' 子目录下
        - Markdown 文件使用与 源文件 相同的名称，但扩展名改为 .md
    """
    try:
        backend = get_backend_per_thread({})
        if not backend:
            return {
                "success": False,
                "error": f"cannot find backend: {source_path}",
                "source_path": source_path,
            }

        working_dir = str(backend._resolve_path('.'))

        # word文件转换成pdf再转换成md
        source_pathlib = Path(source_path)
        if source_pathlib.suffix.lower() in ['.doc', '.docx']:
            # Convert Word to PDF first
            pdf_path = str(source_pathlib.with_suffix('.pdf'))
            try:
                word_to_pdf(working_dir, _trip(source_path), _trip(pdf_path))
                # Update source_path to use the converted PDF
                source_path = pdf_path
            except Exception as e:
                pass

        # Determine output file path
        output_file = str(Path(source_path).with_suffix(".md"))

        # Perform conversion
        try:
            if generate_picture_images and do_formula_enrichment:
                DOCLING_LLM_CONVERTER.convert(
                    working_dir=working_dir,
                    source_file=_trip(source_path),
                    output_file=_trip(output_file)
                )
            elif generate_picture_images:
                DOCLING_IMAGE_CONVERTER.convert(
                    working_dir=working_dir,
                    source_file=_trip(source_path),
                    output_file=_trip(output_file),
                )
            elif do_formula_enrichment:
                DOCLING_LLM_CONVERTER.convert(
                    working_dir=working_dir,
                    source_file=_trip(source_path),
                    output_file=_trip(output_file),
                )
            else:
                DOCLING_FAST_CONVERTER.convert(
                    working_dir=working_dir,
                    source_file=_trip(source_path),
                    output_file=_trip(output_file)
                )
        except Exception as e:
            return {
                "success": False,
                "error": f"file conversion error: {str(e)}",
                "source_path": source_path,
            }

        return {
            "success": True,
            "source_path": source_path,
            "output_file": output_file
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"PDF conversion error: {str(e)}",
            "source_path": source_path,
        }


@tool(parse_docstring=True)
def convert_pdf_to_markdown(
        source_path: str,
) -> dict[str, Any]:
    """将 PDF 文件转换为 Markdown 格式。

    保留了原始文档的布局格式。转换后会生成与源文件同名但扩展名为 .md 的文件。

    Args:
        source_path: 要转换的 PDF 文件路径

    Returns:
        包含以下内容的字典：
        - success: 转换是否成功
        - source_path: 源 PDF 文件的路径
        - output_file: 生成的 Markdown 文件路径
        - error: 转换失败时的错误信息

    Notes:
        - 使用 -layout 参数保留原始布局
        - 如果目标 Markdown 文件已存在，则直接使用现有文件
        - Markdown 文件使用与源文件相同的名称，但扩展名改为 .md
    """
    try:
        backend = get_backend_per_thread({})

        # 解析路径
        source_pathlib = backend._resolve_path(source_path)

        # 检查是否为 PDF 文件
        if not source_pathlib.suffix.lower() == '.pdf':
            return {
                "success": False,
                "error": f"source file is not a PDF: {source_path}",
                "source_path": source_path,
            }

        # 检查源文件是否存在
        if not source_pathlib.exists():
            return {
                "success": False,
                "error": f"source file does not exist: {source_path}",
                "source_path": source_path,
            }

        # 确定 Markdown 输出路径
        markdown_path = source_pathlib.with_suffix(".md")

        # 如果 Markdown 文件不存在，则进行转换
        if not markdown_path.exists():
            try:
                subprocess.run(
                    ['pdftotext', '-layout', str(source_pathlib), str(markdown_path)],
                    check=True
                )
            except Exception as e:
                return {
                    "success": False,
                    "error": f"pdftotext conversion failed: {str(e)}",
                    "source_path": source_path,
                }

        # 检查转换后的文件是否存在
        if not markdown_path.exists():
            return {
                "success": False,
                "error": f"markdown file was not created: {markdown_path}",
                "source_path": source_path,
            }

        return {
            "success": True,
            "source_path": source_path,
            "output_file": str(markdown_path)
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"PDF to Markdown conversion error: {str(e)}",
            "source_path": source_path,
        }


def _trip(path):
    """
    去除路径开头的 / 或 ./ 或 ../
    """
    if path is None:
        return path
    return path.lstrip("/").lstrip("./").lstrip("../")
