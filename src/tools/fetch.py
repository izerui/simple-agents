"""
获取网页内容
"""
from typing import Any

import httpx
from httpx import Timeout
from langchain_core.tools import tool
from markdownify import markdownify


@tool(parse_docstring=True)
def fetch_markdown(url: str) -> dict[str, Any]:
    """从 URL 获取内容并将 HTML 转换为 Markdown 格式。

    该工具获取网页内容并将其转换为清晰的 Markdown 文本，
    使 HTML 内容易于阅读和处理。收到 Markdown 后，
    您必须将信息综合成自然、有益的响应给用户。

    Args:
        url: 要获取的 URL（必须是有效的 HTTP/HTTPS URL）

    Returns:
        包含以下内容的字典：
        - success: 请求是否成功
        - url: 重定向后的最终 URL
        - markdown_content: 转换为 Markdown 的页面内容
        - status_code: HTTP 状态码
        - content_length: Markdown 内容的字符长度

    重要提示：使用此工具后：
    1. 通读 Markdown 内容
    2. 提取回答用户问题的相关信息
    3. 将其综合成清晰的自然语言响应
    4. 除非明确要求，否则绝不向用户展示原始 Markdown
    """
    try:
        # 先发送 HEAD 请求检测 Content-Type
        head_response = httpx.head(
            url,
            timeout=Timeout(timeout=5.0),
            headers={"User-Agent": "Mozilla/5.0 (compatible; DeepAgents/1.0)"},
            follow_redirects=True,
        )
        
        # 检查 Content-Type 是否为文本类内容
        content_type = head_response.headers.get("Content-Type", "").lower()
        
        # 允许的文本类型：text/html, text/plain, application/json, application/xml 等
        text_content_types = [
            "text/html",
            "text/plain",
            "text/css",
            "text/csv",
            "text/javascript",
            "text/xml",
            "text/vcard",
            "text/calendar",
            "text/x-markdown",
            "text/x-log",
            "application/json",
            "application/xml",
            "application/xhtml+xml",
            "text/markdown",
        ]
        
        # 检查是否为允许的文本类型
        is_text_content = any(allowed_type in content_type for allowed_type in text_content_types)
        
        # 拒绝二进制类型：application/zip, application/octet-stream, video/*, audio/*, image/* 等
        binary_content_types = [
            "application/zip",
            "application/octet-stream",
            "application/x-zip-compressed",
            "application/x-rar-compressed",
            "application/x-7z-compressed",
            "application/x-gtar",
            "application/x-tar",
            "application/x-gzip",
            "video/",
            "audio/",
            "image/",
            "application/pdf",
            "application/msword",
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument",
        ]
        
        is_binary_content = any(binary_type in content_type for binary_type in binary_content_types)
        
        if is_binary_content or not is_text_content:
            return {
                "success": False,
                "error": f"Unsupported content type: {content_type}. Only text-based content (HTML, plain text, JSON, etc.) can be fetched.",
                "url": url,
                "content_type": content_type,
            }
        
        response = httpx.get(
            url,
            timeout=Timeout(timeout=15.0),
            headers={"User-Agent": "Mozilla/5.0 (compatible; DeepAgents/1.0)"},
            follow_redirects=True,
        )
        response.raise_for_status()

        # Convert HTML content to markdown
        markdown_content = markdownify(response.text)

        return {
            "success": True,
            "url": str(response.url),
            "markdown_content": markdown_content,
            "status_code": response.status_code,
            "content_length": len(markdown_content),
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Fetch URL error: {e!s}",
            "url": url
        }
