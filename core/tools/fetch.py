"""
获取网页内容
"""
from typing import Any

import httpx
from langchain_core.tools import tool
from markdownify import markdownify


@tool(parse_docstring=True)
def fetch_markdown(url: str, timeout: int = 30) -> dict[str, Any]:
    """从 URL 获取内容并将 HTML 转换为 Markdown 格式。

    该工具获取网页内容并将其转换为清晰的 Markdown 文本，
    使 HTML 内容易于阅读和处理。收到 Markdown 后，
    您必须将信息综合成自然、有益的响应给用户。

    Args:
        url: 要获取的 URL（必须是有效的 HTTP/HTTPS URL）
        timeout: 请求超时时间（秒）（默认：30）

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
        response = httpx.get(
            url,
            timeout=timeout,
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
