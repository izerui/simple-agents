"""
转换工具
"""
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from core.converters.pdf import PDF2Markdown


@tool(parse_docstring=True)
def convert_pdf_to_markdown(pdf_path: str) -> dict[str, Any]:
    """将 PDF 文件转换为 Markdown 格式以便研究。

    该工具将 PDF 文档转换为 Markdown 格式，保留标题、段落、图片和其他格式。
    转换器使用 pdfplumber 进行文本提取，使用 pymupdf 处理图片。

    行为说明：如果目标 .md 文件已存在，该工具将直接返回成功而不执行任何操作（幂等性）。

    Args:
        pdf_path: 要转换的 PDF 文件路径（相对路径）

    Returns:
        包含以下内容的字典：
        - success: 转换是否成功
        - pdf_path: PDF 文件的路径
        - output_file: 生成的 Markdown 文件路径
        - images_extracted: 提取的图片数量
        - error: 转换失败时的错误信息

    Notes:
        - 图片提取到 PDF 同目录下的 'images' 子目录
        - Markdown 文件使用与 PDF 相同的名称，但扩展名改为 .md
        - 转换器会根据字体大小和加粗格式自动检测标题
    """
    try:
        # Resolve absolute path
        pdf_file = Path(pdf_path)

        # Check if PDF exists
        if not pdf_file.exists():
            return {
                "success": False,
                "error": f"PDF file not found: {pdf_path}",
                "pdf_path": str(pdf_file),
            }

        # Check if it's a PDF file
        if pdf_file.suffix.lower() != ".pdf":
            return {
                "success": False,
                "error": f"File is not a PDF: {pdf_path}",
                "pdf_path": str(pdf_file),
            }

        # Determine output file path
        output_file = pdf_file.with_suffix(".md")

        # Check if Markdown file already exists
        if output_file.exists():
            return {
                "success": True,
                "message": "File already ready",
                "pdf_path": str(pdf_file),
                "output_file": str(output_file),
            }

        # Create converter instance
        converter = PDF2Markdown(debug=False)

        # Perform conversion
        result = converter.convert(str(pdf_file), str(output_file))

        if result.startswith("错误:"):
            return {
                "success": False,
                "error": result,
                "pdf_path": str(pdf_file),
            }

        # Read the output file to get content length and count images
        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Count images (look for image markdown syntax)
        images_count = content.count("![图片]")

        return {
            "success": True,
            "pdf_path": str(pdf_file),
            "output_file": str(output_file),
            "content_length": len(content),
            "images_extracted": images_count,
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"PDF conversion error: {str(e)}",
            "pdf_path": pdf_path,
        }
