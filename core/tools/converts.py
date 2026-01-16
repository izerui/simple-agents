"""
转换工具
"""
from pathlib import Path
from typing import Any

from langchain_core.tools import tool
from langgraph.config import get_config

from core.converters.docx import DOCX2Markdown
from core.converters.pdf import PDF2Markdown
from core.utils import get_backend_per_thread


@tool(parse_docstring=True)
def convert_pdf_to_markdown(pdf_path: str) -> dict[str, Any]:
    """将 PDF 文件转换为 Markdown 格式以便研究。

    该工具将 PDF 文档转换为 Markdown 格式

    Args:
        pdf_path: 要转换的 PDF 文件路径

    Returns:
        包含以下内容的字典：
        - success: 转换是否成功
        - pdf_path: PDF 文件的路径
        - output_file: 生成的 Markdown 文件路径
        - error: 转换失败时的错误信息

    Notes:
        - 图片提取到 PDF 同目录下的 'images' 子目录
        - Markdown 文件使用与 PDF 相同的名称，但扩展名改为 .md
    """
    try:
        backend = get_backend_per_thread({})
        if not backend:
            return {
                "success": False,
                "error": f"cannot find backend: {pdf_path}",
                "pdf_path": pdf_path,
            }

        # Determine output file path
        output_file = str(Path(pdf_path).with_suffix(".md"))

        # Create converter instance
        converter = PDF2Markdown()

        # Perform conversion
        try:
            converter.convert(pdf_path, output_file, work_dir=str(backend._resolve_path('.')))
        except Exception as e:
            return {
                "success": False,
                "error": f"PDF conversion error: {str(e)}",
                "pdf_path": pdf_path,
            }

        return {
            "success": True,
            "pdf_path": pdf_path,
            "output_file": output_file
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"PDF conversion error: {str(e)}",
            "pdf_path": pdf_path,
        }


@tool(parse_docstring=True)
def convert_docx_to_markdown(docx_path: str) -> dict[str, Any]:
    """将 Word 文档（DOCX）转换为 Markdown 格式以便研究。

    该工具将 Word 文档转换为 Markdown 格式

    Args:
        docx_path: 要转换的 DOCX 文件路径

    Returns:
        包含以下内容的字典：
        - success: 转换是否成功
        - docx_path: DOCX 文件的路径
        - output_file: 生成的 Markdown 文件路径
        - error: 转换失败时的错误信息

    Notes:
        - Markdown 文件使用与 DOCX 相同的名称，但扩展名改为 .md
    """
    try:
        backend = get_backend_per_thread(get_config())
        if not backend:
            return {
                "success": False,
                "error": f"cannot find backend: {docx_path}",
                "docx_path": docx_path,
            }

        # Determine output file path
        output_file = str(Path(docx_path).with_suffix(".md"))

        # Create converter instance
        converter = DOCX2Markdown()

        # Perform conversion
        try:
            converter.convert(docx_path, output_file, work_dir=str(backend._resolve_path('.')))
        except Exception as e:
            return {
                "success": False,
                "error": f"DOCX conversion error: {str(e)}",
                "docx_path": docx_path,
            }

        return {
            "success": True,
            "docx_path": docx_path,
            "output_file": output_file,
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"DOCX conversion error: {str(e)}",
            "docx_path": docx_path,
        }
