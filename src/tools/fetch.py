"""
获取网页内容 - 使用浏览器服务（异步版本）

此模块通过 HTTP 与浏览器服务通信，
实现高并发的网页抓取功能。

架构:
    fetch_url (主进程) → HTTP 请求 → 浏览器服务
"""
import asyncio
import base64
import logging
import os
import random
import re
import time
import uuid
from typing import Any

import aiofiles

from langchain_core.tools import tool
from src.utils.util import get_backend_per_thread

logger = logging.getLogger(__name__)

# 浏览器服务配置
# 从环境变量读取浏览器服务地址，默认为本地开发环境
# 生产环境: docker-compose 中配置为 http://browser-service:2025
# 开发环境: 可以配置为 http://127.0.0.1:2025
BROWSER_SERVICE_URL = os.getenv("BROWSER_SERVICE_URL", "http://127.0.0.1:2025")
BROWSER_SERVICE_TIMEOUT = int(os.getenv("BROWSER_SERVICE_TIMEOUT", "60"))  # 请求超时（秒）


async def async_save_fetch_result(url: str, service_result: dict[str, Any]) -> dict[str, Any]:
    """保存浏览器服务返回的结果到文件（异步版本）。

    Args:
        url: 原始请求的 URL
        service_result: 浏览器服务返回的结果

    Returns:
        包含本地文件路径的字典
    """
    backend = get_backend_per_thread({})

    # 获取服务返回的数据
    title = service_result.get("title", "无标题")
    markdown_content = service_result.get("markdown_content", "")
    screenshot_base64 = service_result.get("screenshot_base64", "")

    # 并发创建目录
    capture_dir = backend._resolve_path(".capture")
    markdown_dir = backend._resolve_path("fetch_url")

    await asyncio.gather(
        async_makedirs(capture_dir),
        async_makedirs(markdown_dir)
    )

    # 并发保存截图和 Markdown
    screenshot_filename = None

    async def save_screenshot() -> str | None:
        nonlocal screenshot_filename
        if not screenshot_base64:
            return None

        screenshot_uuid = str(uuid.uuid4())
        screenshot_filename = f".capture/{screenshot_uuid}.png"
        screenshot_path = backend._resolve_path(screenshot_filename)

        try:
            screenshot_bytes = base64.b64decode(screenshot_base64)
            async with aiofiles.open(screenshot_path, 'wb') as f:
                await f.write(screenshot_bytes)
            logger.info(f"Screenshot saved to {screenshot_filename}")
            return screenshot_filename
        except Exception as e:
            logger.warning(f"Failed to save screenshot: {e}")
            return None

    async def save_markdown() -> tuple[str, int]:
        # 清理内容
        cleaned_content = re.sub(r'\n{3,}', '\n\n', markdown_content)
        cleaned_content = re.sub(r'^\s+$/gm', '', cleaned_content)
        cleaned_content = cleaned_content.strip()

        # 生成文件名：title + 5位随机字符串
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
        safe_title = re.sub(r'\s+', '_', safe_title)
        random_suffix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=5))
        markdown_filename = f"{safe_title}_{random_suffix}.md"
        markdown_file_path = os.path.join(markdown_dir, markdown_filename)

        # 异步写入文件
        async with aiofiles.open(markdown_file_path, 'w', encoding='utf-8') as f:
            await f.write(cleaned_content)

        # 计算相对路径用于返回
        relative_file_path = f"/fetch_url/{markdown_filename}"
        return relative_file_path, len(cleaned_content)

    # 并发执行保存操作
    results = await asyncio.gather(
        save_screenshot(),
        save_markdown(),
        return_exceptions=True
    )

    # 处理结果
    screenshot_result = results[0]
    markdown_result = results[1]

    if isinstance(screenshot_result, Exception):
        logger.warning(f"Screenshot save failed: {screenshot_result}")
        screenshot_filename = None
    elif screenshot_result:
        screenshot_filename = screenshot_result

    if isinstance(markdown_result, Exception):
        raise markdown_result

    relative_file_path, content_length = markdown_result

    return {
        "file_path": relative_file_path,
        "url_capture": f"/{screenshot_filename}" if screenshot_filename else None,
        "title": title,
        "content_length": content_length,
    }


async def async_makedirs(path: str) -> None:
    """异步创建目录（使用 asyncio.to_thread）。

    Args:
        path: 要创建的目录路径
    """
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, os.makedirs, path, 0o777, True)


async def fetch_from_browser_service(url: str) -> dict[str, Any]:
    """从浏览器服务获取网页内容（异步版本）。

    Args:
        url: 要获取的网页地址

    Returns:
        包含网页信息的字典
    """
    import httpx

    logger.info(f"Fetching {url}")

    try:
        async with httpx.AsyncClient(timeout=BROWSER_SERVICE_TIMEOUT) as client:
            response = await client.post(
                f"{BROWSER_SERVICE_URL}/fetch_url",
                json={"url": url, "wait_time": 1000}
            )
            response.raise_for_status()
            service_result = response.json()

        logger.info(f"Fetch result for {url}: success={service_result.get('success')}")

        # 如果服务返回失败，直接返回错误
        if not service_result.get("success"):
            return {
                "success": False,
                "url": url,
                "error": service_result.get("error", "未知错误")
            }

        # 保存结果到文件
        file_info = await async_save_fetch_result(url, service_result)

        # 返回和之前一样的结构
        return {
            "success": True,
            "url": url,
            "title": file_info["title"],
            "file_path": file_info["file_path"],
            "content_length": file_info["content_length"],
            "fetched_at": service_result.get("fetched_at", time.strftime("%Y-%m-%d %H:%M:%S")),
            "url_capture": file_info["url_capture"],
            "message": f"已成功获取 {url} 的内容，并保存到 {file_info['file_path']}"
        }

    except httpx.ConnectError:
        logger.error(f"无法连接到浏览器服务 ({BROWSER_SERVICE_URL})，请确保服务已启动")
        return {
            "success": False,
            "url": url,
            "error": f"无法连接到浏览器服务，请确保服务在 {BROWSER_SERVICE_URL} 运行"
        }
    except httpx.TimeoutException:
        logger.error(f"请求超时: {url}")
        return {
            "success": False,
            "url": url,
            "error": f"请求超时（超过 {BROWSER_SERVICE_TIMEOUT} 秒）"
        }
    except httpx.HTTPError as e:
        logger.error(f"请求失败: {e}")
        return {
            "success": False,
            "url": url,
            "error": f"请求失败: {str(e)}"
        }
    except Exception as e:
        logger.error(f"未知错误: {e}")
        return {
            "success": False,
            "url": url,
            "error": f"未知错误: {str(e)}"
        }


@tool(parse_docstring=True)
async def fetch_url(url: str) -> dict[str, Any]:
    """获取网页内容并转换为易读的 Markdown 格式（使用浏览器服务）。

    这是一个网页抓取工具，使用浏览器服务获取内容，可以处理各种网站，
    包括有反爬虫保护的网站。工具会将结果转换为清晰的 Markdown 格式供你阅读和使用。

    架构说明:
        - 使用独立的浏览器服务（browser-fetch）处理抓取任务
        - 支持高并发（默认 5 个浏览器实例，每实例 10 并发）
        - 通过 HTTP 通信，简单高效
        - 返回 Markdown 内容和 Base64 截图
        - 内部使用异步实现，提高并发性能

    何时使用此工具：
    - 用户要求获取、总结或分析某个网页的内容
    - 需要提取网页中的特定信息（如文章、新闻、数据等）
    - 用户提供的 URL 需要访问并获取内容
    - 需要查看动态加载的页面内容

    使用指南：
    1. 获取内容后，根据 file_path 字段读取保存的 markdown 文件
    2. 提取用户需要的信息，用清晰、自然的语言总结和呈现给用户
    3. 不要直接展示原始 Markdown 代码，除非用户明确要求
    4. 如果内容很长，提取关键信息进行总结

    Args:
        url: 要获取的网页地址（必须是 http:// 或 https:// 开头的有效 URL）

    Returns:
        包含网页信息的字典，主要字段：
        - success: 是否成功获取内容（True/False）
        - file_path: markdown 文件的路径（内容已保存到此文件，请使用 read_tool 读取）
        - title: 网页标题
        - url: 最终访问的 URL
        - content_length: Markdown 内容的字符长度
        - fetched_at: 内容获取时间（格式：YYYY-MM-DD HH:MM:SS）
        - url_capture: 网页截图路径
        - message: 操作结果消息
        - error: 失败时的错误信息（如果 success 为 False）
    """
    # 直接调用异步函数
    try:
        return await fetch_from_browser_service(url)
    except Exception as e:
        logger.error(f"fetch_url 执行失败: {e}", exc_info=True)
        return {
            "success": False,
            "url": url,
            "error": f"执行失败: {str(e)}"
        }
