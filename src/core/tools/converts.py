"""
转换成 Markdown 工具
"""
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from src.core.converters._docling import DOCLING_CONVERTER
from src.core.utils import get_backend_per_thread


@tool(parse_docstring=True)
def convert_to_markdown(source_path: str) -> dict[str, Any]:
    """将 PDF, DOCX, XLSX, PPTX, AsciiDoc 文件转换为 Markdown 格式以便研究。

    该工具将 PDF 文档转换为 Markdown 格式

    Args:
        source_path: 要转换的文件路径

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

        # Determine output file path
        output_file = str(Path(source_path).with_suffix(".md"))

        # Perform conversion
        try:
            DOCLING_CONVERTER.convert(
                working_dir=str(backend._resolve_path('.')),
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


def _trip(path):
    """
    去除路径开头的 / 或 ./ 或 ../
    """
    if path is None:
        return path
    return path.lstrip("/").lstrip("./").lstrip("../")
