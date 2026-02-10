"""
转换成 Markdown 工具
"""
import subprocess
from pathlib import Path
from typing import Any

import requests
from langchain_core.tools import tool

from src.utils._word_to_pdf import word_to_pdf
from src.utils.util import get_backend_per_thread


@tool(parse_docstring=True)
def convert_to_markdown(
        source_path: str,
        generate_picture_images: bool = False,
        do_formula_enrichment: bool = False,
) -> dict[str, Any]:
    """将各种文件格式转换为 Markdown 格式以便研究。

    该工具将文档转换为 Markdown 格式。根据用户的问题内容来决定是否启用特殊功能：

    启用图片提取的时机：当用户问题涉及图片、图表、截图、图形、插图、示意图、流程图、截图中的文字、界面展示等视觉内容时，应将 generate_picture_images 设为 True

    启用公式识别的时机：当用户问题涉及数学公式、方程、不等式、符号、微积分、数学表达式、化学方程式、物理公式等内容时，应将 do_formula_enrichment 设为 True

    支持的文件格式：
    - PDF、DOC、DOCX、PPTX、PNG、JPG、JPEG、GIF、BMP、AsciiDoc
    - 所有格式都支持图片提取和公式识别功能

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
        - PDF 和 Word 文件使用本地转换工具，不支持图片提取和公式识别参数
        - 其他格式使用远程 API 转换，支持图片提取和公式识别
        - Markdown 文件使用与源文件相同的名称，但扩展名改为 .md
    """
    try:
        backend = get_backend_per_thread({})
        if not backend:
            return {
                "success": False,
                "error": f"cannot find backend: {source_path}",
                "source_path": source_path,
            }

        source_pathlib = backend._resolve_path(source_path)

        # 检查源文件是否存在
        if not source_pathlib.exists():
            return {
                "success": False,
                "error": f"source file does not exist: {source_path}",
                "source_path": source_path,
            }

        # PDF 文件使用专用转换方法
        if source_pathlib.suffix.lower() == '.pdf':
            return _convert_pdf_to_markdown(
                source_path=source_path,
                generate_picture_images=generate_picture_images,
                do_formula_enrichment=do_formula_enrichment,
            )

        # Word 文件使用专用转换方法
        if source_pathlib.suffix.lower() in ['.doc', '.docx']:
            return _convert_word_to_markdown(
                source_path=source_path,
                generate_picture_images=generate_picture_images,
                do_formula_enrichment=do_formula_enrichment,
            )

        # 其他文件格式使用远程 API 转换
        return _convert_via_remote_api(
            source_path=source_path,
            generate_picture_images=generate_picture_images,
            do_formula_enrichment=do_formula_enrichment,
        )

    except Exception as e:
        return {
            "success": False,
            "error": f"conversion error: {str(e)}",
            "source_path": source_path,
        }


def _convert_word_to_markdown(
        source_path: str,
        generate_picture_images: bool = False,
        do_formula_enrichment: bool = False,
) -> dict[str, Any]:
    """将 Word 文件（DOC/DOCX）转换为 Markdown 格式。

    该工具先将 Word 文件转换为 PDF，然后将 PDF 转换为 Markdown 格式，
    保留了原始文档的布局格式。转换后会生成与源文件同名但扩展名为 .md 的文件。

    Args:
        source_path: 要转换的 Word 文件路径（.doc 或 .docx）
        generate_picture_images: 是否识别并提取图片（根据用户问题是否涉及视觉内容决定）
        do_formula_enrichment: 是否识别公式（根据用户问题是否涉及数学公式决定）

    Returns:
        包含以下内容的字典：
        - success: 转换是否成功
        - source_path: 源 Word 文件的路径
        - output_file: 生成的 Markdown 文件路径
        - error: 转换失败时的错误信息

    Notes:
        - 先将 Word 转换为 PDF，再转换为 Markdown
        - 如果目标 Markdown 文件已存在，则直接使用现有文件
        - Markdown 文件使用与源文件相同的名称，但扩展名改为 .md
    """
    try:
        backend = get_backend_per_thread({})

        # 解析路径
        source_pathlib = backend._resolve_path(source_path)
        working_dir = str(backend._resolve_path('.'))

        # 检查是否为 Word 文件
        if source_pathlib.suffix.lower() not in ['.doc', '.docx']:
            return {
                "success": False,
                "error": f"source file is not a Word document: {source_path}",
                "source_path": source_path,
            }

        # 检查源文件是否存在
        if not source_pathlib.exists():
            return {
                "success": False,
                "error": f"source file does not exist: {source_path}",
                "source_path": source_path,
            }

        # 先转换为 PDF（使用 source_path 改后缀名）
        pdf_path = source_path.rsplit('.', 1)[0] + '.pdf'
        try:
            word_to_pdf(working_dir, _trip(source_path), _trip(pdf_path))
        except Exception as e:
            return {
                "success": False,
                "error": f"Word to PDF conversion failed: {str(e)}",
                "source_path": source_path,
            }

        # 再调用 PDF 转 Markdown 的内部实现
        result = _convert_pdf_to_markdown(
            pdf_path,
            generate_picture_images=generate_picture_images,
            do_formula_enrichment=do_formula_enrichment,
        )

        # 确保返回的 source_path 是原始 Word 文件路径，而不是 PDF 路径
        if "source_path" in result:
            result["source_path"] = source_path

        return result

    except Exception as e:
        return {
            "success": False,
            "error": f"Word to Markdown conversion error: {str(e)}",
            "source_path": source_path,
        }


def _trip(path):
    """
    去除路径开头的 / 或 ./ 或 ../
    """
    if path is None:
        return path
    return path.lstrip("/").lstrip("./").lstrip("../")


def _convert_via_remote_api(
        source_path: str,
        generate_picture_images: bool = False,
        do_formula_enrichment: bool = False,
) -> dict[str, Any]:
    """使用远程 API 将文件转换为 Markdown 格式。

    Args:
        source_path: 源文件路径
        generate_picture_images: 是否识别并提取图片
        do_formula_enrichment: 是否识别公式

    Returns:
        包含转换结果的字典
    """
    backend = get_backend_per_thread({})
    source_pathlib = backend._resolve_path(source_path)
    # 基于 source_path 字符串生成 markdown 路径，避免路径解析问题
    markdown_path = backend._resolve_path(source_path.rsplit('.', 1)[0] + '.md')
    output_file = source_path.rsplit('.', 1)[0] + '.md'
    api_base_url = "https://dcca.hhstu.edu.cn/transfer"

    # 计算超时时间（AI 功能需要更长时间）
    timeout = 1800 if (generate_picture_images or do_formula_enrichment) else 300

    try:
        # 使用远程 API 进行转换
        with open(source_pathlib, 'rb') as f:
            files = {'file': (source_pathlib.name, f, 'application/octet-stream')}
            data = {
                'guess_image': 'true' if generate_picture_images else 'false',
                'guess_formula': 'true' if do_formula_enrichment else 'false'
            }
            response = requests.post(
                f"{api_base_url}/api/to-markdown",
                files=files,
                data=data,
                timeout=timeout,
                verify=False
            )

        response.raise_for_status()

        # 检查内容类型，拒绝 HTML 响应
        content_type = response.headers.get('Content-Type', '')
        if 'text/html' in content_type.lower():
            return {
                "success": False,
                "error": "API returned HTML instead of Markdown (possible authentication error)",
                "source_path": source_path,
            }

        # 保存 Markdown 内容
        with open(markdown_path, 'wb') as f:
            f.write(response.content)

        return {
            "success": True,
            "source_path": source_path,
            "output_file": output_file
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"remote API conversion failed: {str(e)}",
            "source_path": source_path,
        }


def _convert_pdf_to_markdown(source_path: str,
                             generate_picture_images: bool = False,
                             do_formula_enrichment: bool = False, ) -> dict[str, Any]:
    """PDF 转 Markdown 的内部实现函数（不被 @tool 装饰）"""
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

        # 如果需要图片提取或公式识别，使用远程 API 转换
        if generate_picture_images or do_formula_enrichment:
            return _convert_via_remote_api(
                source_path=source_path,
                generate_picture_images=generate_picture_images,
                do_formula_enrichment=do_formula_enrichment,
            )

        # 确定 Markdown 输出路径（基于 source_path 字符串，避免路径解析问题）
        markdown_path = backend._resolve_path(source_path.rsplit('.', 1)[0] + '.md')
        output_file = source_path.rsplit('.', 1)[0] + '.md'

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
            "output_file": output_file
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"PDF to Markdown conversion error: {str(e)}",
            "source_path": source_path,
        }
