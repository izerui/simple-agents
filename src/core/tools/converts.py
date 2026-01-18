"""
转换成 Markdown 工具
"""
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from src.core.converters._docling import DOCLING_FAST_CONVERTER, DOCLING_IMAGE_CONVERTER, \
    DOCLING_FORMULA_CONVERTER, DOCLING_FULL_CONVERTER
from src.core.utils import get_backend_per_thread


@tool(parse_docstring=True)
def convert_to_markdown(
        source_path: str,
        generate_picture_images: bool = False,
        do_formula_enrichment: bool = False,
) -> dict[str, Any]:
    """将 PDF, DOCX, XLSX, PPTX, AsciiDoc 文件转换为 Markdown 格式以便研究。

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

        # Determine output file path
        output_file = str(Path(source_path).with_suffix(".md"))

        # Perform conversion
        try:
            if generate_picture_images and do_formula_enrichment:
                DOCLING_FULL_CONVERTER.convert(
                    working_dir=str(backend._resolve_path('.')),
                    source_file=_trip(source_path),
                    output_file=_trip(output_file)
                )
            elif generate_picture_images:
                DOCLING_IMAGE_CONVERTER.convert(
                    working_dir=str(backend._resolve_path('.')),
                    source_file=_trip(source_path),
                    output_file=_trip(output_file),
                )
            elif do_formula_enrichment:
                DOCLING_FORMULA_CONVERTER.convert(
                    working_dir=str(backend._resolve_path('.')),
                    source_file=_trip(source_path),
                    output_file=_trip(output_file),
                )
            else:
                DOCLING_FAST_CONVERTER.convert(
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
