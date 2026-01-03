"""
转换工具
"""
from typing import Any

from langchain_core.tools import tool

from core.converters.docx import DOCX2Markdown
from core.converters.pdf import PDF2Markdown
from deepagents.backends.filesystem_async import AsyncFilesystemBackend


@tool(parse_docstring=True)
def convert_pdf_to_markdown(pdf_path: str, _backend: AsyncFilesystemBackend = None) -> dict[str, Any]:
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
        - abs_output_file: 生成的 Markdown 文件路径
        - images_extracted: 提取的图片数量
        - error: 转换失败时的错误信息

    Notes:
        - 图片提取到 PDF 同目录下的 'images' 子目录
        - Markdown 文件使用与 PDF 相同的名称，但扩展名改为 .md
        - 转换器会根据字体大小和加粗格式自动检测标题
    """
    try:
        if not _backend:
            return {
                "success": False,
                "error": f"cannot find backend: {pdf_path}",
                "pdf_path": pdf_path,
            }
        # Resolve absolute path
        abs_pdf_file = _backend.prepend_thread_dir(pdf_path)

        # Check if PDF exists
        if not abs_pdf_file.exists():
            return {
                "success": False,
                "error": f"PDF file not found: {pdf_path}",
                "pdf_path": _backend.remove_thread_dir_prefix(pdf_path),
            }

        # Check if it's a PDF file
        if abs_pdf_file.suffix.lower() != ".pdf":
            return {
                "success": False,
                "error": f"File is not a PDF: {pdf_path}",
                "pdf_path": _backend.remove_thread_dir_prefix(pdf_path),
            }

        # Determine output file path
        abs_output_file = abs_pdf_file.with_suffix(".md")

        # Check if Markdown file already exists
        if abs_output_file.exists():
            return {
                "success": True,
                "message": "File already ready",
                "pdf_path": _backend.remove_thread_dir_prefix(pdf_path),
                "abs_output_file": _backend.remove_thread_dir_prefix(str(abs_output_file)),
            }

        # Create converter instance
        converter = PDF2Markdown()

        # Perform conversion
        try:
            converter.convert(str(abs_pdf_file), str(abs_output_file))
        except Exception as e:
            return {
                "success": False,
                "error": f"PDF conversion error: {str(e)}",
                "pdf_path": _backend.remove_thread_dir_prefix(pdf_path),
            }

        # Read the output file to get content length and count images
        with open(abs_output_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Count images (look for image markdown syntax)
        images_count = content.count("![图片]")

        return {
            "success": True,
            "pdf_path": _backend.remove_thread_dir_prefix(pdf_path),
            "abs_output_file": _backend.remove_thread_dir_prefix(str(abs_output_file)),
            "content_length": len(content),
            "images_extracted": images_count,
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"PDF conversion error: {str(e)}",
            "pdf_path": _backend.remove_thread_dir_prefix(pdf_path),
        }


@tool(parse_docstring=True)
def convert_docx_to_markdown(docx_path: str, _backend: AsyncFilesystemBackend = None) -> dict[str, Any]:
    """将 Word 文档（DOCX）转换为 Markdown 格式以便研究。

    该工具将 Word 文档转换为 Markdown 格式，保留标题、段落、列表、表格和其他格式。
    转换器使用 mammoth 进行 DOCX 到 HTML 的转换，使用 html2text 将 HTML 转换为 Markdown。

    行为说明：如果目标 .md 文件已存在，该工具将直接返回成功而不执行任何操作（幂等性）。

    Args:
        docx_path: 要转换的 DOCX 文件路径（相对路径）

    Returns:
        包含以下内容的字典：
        - success: 转换是否成功
        - docx_path: DOCX 文件的路径
        - output_file: 生成的 Markdown 文件路径
        - content_length: 转换后内容长度
        - messages: 转换过程中的消息列表
        - error: 转换失败时的错误信息

    Notes:
        - Markdown 文件使用与 DOCX 相同的名称，但扩展名改为 .md
        - 转换器会自动处理标题、段落、列表、表格和图片
        - 转换过程中可能会生成警告或信息消息，这些会被包含在返回结果中
    """
    try:
        if not _backend:
            return {
                "success": False,
                "error": f"cannot find backend: {docx_path}",
                "docx_path": docx_path,
            }
        # Resolve absolute path
        abs_docx_file = _backend.prepend_thread_dir(docx_path)

        # Check if DOCX exists
        if not abs_docx_file.exists():
            return {
                "success": False,
                "error": f"DOCX file not found: {docx_path}",
                "docx_path": _backend.remove_thread_dir_prefix(docx_path),
            }

        # Check if it's a DOCX file
        if abs_docx_file.suffix.lower() != ".docx":
            return {
                "success": False,
                "error": f"File is not a DOCX: {docx_path}",
                "docx_path": _backend.remove_thread_dir_prefix(docx_path),
            }

        # Determine output file path
        output_file = abs_docx_file.with_suffix(".md")

        # Check if Markdown file already exists
        if output_file.exists():
            return {
                "success": True,
                "message": "File already ready",
                "docx_path": _backend.remove_thread_dir_prefix(docx_path),
                "output_file": _backend.remove_thread_dir_prefix(str(output_file)),
            }

        # Create converter instance
        converter = DOCX2Markdown(debug=False)

        # Perform conversion
        try:
            result = converter.convert(str(abs_docx_file), str(output_file))
        except Exception as e:
            return {
                "success": False,
                "error": f"DOCX conversion error: {str(e)}",
                "docx_path": _backend.remove_thread_dir_prefix(docx_path),
            }

        # Read the output file to get content length
        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Get conversion messages
        messages = converter.messages

        return {
            "success": True,
            "docx_path": _backend.remove_thread_dir_prefix(docx_path),
            "output_file": _backend.remove_thread_dir_prefix(str(output_file)),
            "content_length": len(content),
            "messages": messages,
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"DOCX conversion error: {str(e)}",
            "docx_path": _backend.remove_thread_dir_prefix(docx_path),
        }
