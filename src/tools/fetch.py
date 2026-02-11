"""
获取网页内容 - 使用 Playwright 浏览器模式
"""
import random
import re
import time
import uuid
from typing import Any, Optional

from langchain_core.tools import tool
from markdownify import markdownify

from src.utils.util import get_backend_per_thread

# Playwright 相关依赖
PLAYWRIGHT_AVAILABLE = True
PLAYWRIGHT_STEALTH_AVAILABLE = False

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    sync_playwright = None

try:
    from playwright_stealth import Stealth
    PLAYWRIGHT_STEALTH_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_STEALTH_AVAILABLE = False
    Stealth = None


# ==================== 反爬虫工具函数 ====================

# 常用 User-Agent 池
USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    # Firefox on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
]


def get_random_user_agent() -> str:
    """获取随机 User-Agent"""
    return random.choice(USER_AGENTS)


def get_realistic_headers(url: str = "") -> dict[str, str]:
    """
    生成逼真的请求头，模拟真实浏览器

    Args:
        url: 目标URL（用于推断Referer等）

    Returns:
        包含各种请求头的字典
    """
    ua = get_random_user_agent()

    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    # 根据UA添加特定浏览器的请求头
    if "Chrome" in ua:
        headers["sec-ch-ua"] = '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"'
        headers["sec-ch-ua-mobile"] = "?0"
        headers["sec-ch-ua-platform"] = '"Windows"' if "Windows" in ua else '"macOS"'
    elif "Safari" in ua and "Chrome" not in ua:
        headers["sec-ch-ua"] = '"Not_A Brand";v="8", "Chromium";v="120", "Safari";v="120"'

    # 如果提供了URL，设置Referer
    if url:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            headers["Referer"] = f"{parsed.scheme}://{parsed.netloc}/"

    return headers


def is_valid_url(url: str) -> bool:
    """验证URL是否有效"""
    try:
        from urllib.parse import urlparse
        result = urlparse(url)
        return all([result.scheme, result.netloc]) and result.scheme in ['http', 'https']
    except Exception:
        return False


def fetch_with_playwright(url: str) -> dict[str, Any]:
    """
    使用Playwright获取网页内容（增强反爬虫版本 + playwright-stealth）

    模拟真实浏览器行为，包括：
    - 随机视口大小
    - 逼真的User-Agent
    - 完整的浏览器指纹（使用 playwright-stealth）
    - 模拟人类操作延迟
    """
    if not PLAYWRIGHT_AVAILABLE:
        return {
            "success": False,
            "error": "Playwright 未安装，如需使用浏览器模式请运行: pip install playwright && playwright install chromium",
            "url": url
        }

    if not is_valid_url(url):
        return {
            "success": False,
            "error": "无效的URL格式，请提供http或https协议的URL",
            "url": url
        }

    backend = get_backend_per_thread({})

    try:
        with sync_playwright() as p:
            # 获取随机User-Agent
            user_agent = get_random_user_agent()

            # 随机视口大小（常见分辨率）
            viewports = [
                {"width": 1920, "height": 1080},
                {"width": 1680, "height": 1050},
                {"width": 1440, "height": 900},
                {"width": 1366, "height": 768},
                {"width": 1536, "height": 864},
            ]
            viewport = random.choice(viewports)

            # 启动浏览器（更多反检测参数）
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-site-isolation-trials',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                ]
            )

            try:
                # 创建新页面
                page = browser.new_page(
                    viewport=viewport,
                    user_agent=user_agent
                )

                # 使用 playwright-stealth 隐藏浏览器指纹
                if PLAYWRIGHT_STEALTH_AVAILABLE:
                    stealth = Stealth()
                    stealth.apply_stealth_sync(page)

                # 设置额外的请求头
                headers = get_realistic_headers(url)
                page.set_extra_http_headers({
                    k: v for k, v in headers.items()
                    if k not in ['User-Agent', 'Accept-Encoding']  # 避免重复
                })

                # 如果没有 playwright-stealth，使用自定义脚本
                if not PLAYWRIGHT_STEALTH_AVAILABLE:
                    page.add_init_script("""
                        // 覆盖navigator.webdriver
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined
                        });

                        // 覆盖chrome对象
                        window.chrome = {
                            runtime: {}
                        };

                        // 覆盖permissions
                        const originalQuery = window.navigator.permissions.query;
                        window.navigator.permissions.query = (parameters) => (
                            parameters.name === 'notifications' ?
                                Promise.resolve({ state: Notification.permission }) :
                                originalQuery(parameters)
                        );

                        // 覆盖plugins
                        Object.defineProperty(navigator, 'plugins', {
                            get: () => [1, 2, 3, 4, 5]
                        });

                        // 覆盖languages
                        Object.defineProperty(navigator, 'languages', {
                            get: () => ['zh-CN', 'zh', 'en']
                        });
                    """)

                # 加载所有资源，仅阻止媒体文件（视频/音频）
                def route_handler(route):
                    resource_type = route.request.resource_type
                    if resource_type == 'media':
                        route.abort()
                    else:
                        route.continue_()

                page.route("**/*", route_handler)

                # 导航到页面（30秒超时）
                page.goto(url, timeout=30000, wait_until="domcontentloaded")

                # 随机等待时间，模拟人类阅读
                page.wait_for_timeout(random.randint(1500, 3000))

                # 模拟鼠标移动（可选，增加真实性）
                try:
                    page.mouse.move(random.randint(100, 500), random.randint(100, 500))
                except Exception:
                    pass

                # 获取页面标题
                title = page.title() or "无标题"

                # 先截图（此时页面完整，包含 header 等所有元素）
                screenshot_uuid = str(uuid.uuid4())
                screenshot_filename = f".capture/{screenshot_uuid}.png"
                screenshot_path = backend._resolve_path(screenshot_filename)
                screenshot_bytes = page.screenshot(full_page=True)
                with open(screenshot_path, 'wb') as f:
                    f.write(screenshot_bytes)

                # 移除不需要的元素（仅影响文本提取，不影响截图）
                page.evaluate("""
                    () => {
                        const elementsToRemove = document.querySelectorAll(
                            'script, style, nav, header, footer, aside, .advertisement, .ads, .sidebar, .comments, .social-share'
                        );
                        elementsToRemove.forEach(el => el.remove());
                    }
                """)

                # 获取主要内容
                main_content_html = page.evaluate("""
                    () => {
                        const mainContent =
                            document.querySelector('main') ||
                            document.querySelector('article') ||
                            document.querySelector('[role="main"]') ||
                            document.querySelector('.content') ||
                            document.querySelector('#content') ||
                            document.querySelector('.post') ||
                            document.querySelector('.entry-content') ||
                            document.body;

                        return mainContent ? mainContent.innerHTML : document.body.innerHTML;
                    }
                """)

                # 转换为Markdown
                markdown_content = markdownify(main_content_html)

                # 清理内容
                cleaned_content = re.sub(r'\n{3,}', '\n\n', markdown_content)
                cleaned_content = re.sub(r'^\s+$/gm', '', cleaned_content)
                cleaned_content = cleaned_content.strip()

                return {
                    "success": True,
                    "url": url,
                    "title": title,
                    "markdown_content": cleaned_content,
                    "content_length": len(cleaned_content),
                    "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "url_capture": f"/{screenshot_filename}",
                    "message": f"已经成功获取 {url} 的内容。"
                }

            finally:
                browser.close()

    except Exception as e:
        return {
            "success": False,
            "error": f"Playwright获取失败: {str(e)}",
            "url": url
        }


@tool(parse_docstring=True)
def fetch_url(url: str) -> dict[str, Any]:
    """获取网页内容并转换为易读的 Markdown 格式（使用 Playwright）。

    这是一个网页抓取工具，使用浏览器模式获取内容，可以处理各种网站，
    包括有反爬虫保护的网站。工具会将结果转换为清晰的 Markdown 格式供你阅读和使用。

    何时使用此工具：
    - 用户要求获取、总结或分析某个网页的内容
    - 需要提取网页中的特定信息（如文章、新闻、数据等）
    - 用户提供的 URL 需要访问并获取内容
    - 需要查看动态加载的页面内容

    工作方式：
    1. 使用浏览器模式加载页面
    2. 等待页面完全加载
    3. 自动处理反爬虫保护
    4. 截图并提取内容

    Args:
        url: 要获取的网页地址（必须是 http:// 或 https:// 开头的有效 URL）

    Returns:
        包含网页信息的字典，主要字段：
        - success: 是否成功获取内容（True/False）
        - markdown_content: 网页内容的 Markdown 格式文本（这是你最需要的字段）
        - title: 网页标题
        - url: 最终访问的 URL
        - content_length: Markdown 内容的字符长度
        - fetched_at: 内容获取时间（格式：YYYY-MM-DD HH:MM:SS）
        - url_capture: 网页截图路径
        - message: 操作结果消息
        - error: 失败时的错误信息（如果 success 为 False）

    使用指南：
    1. 获取内容后，仔细阅读 markdown_content 字段
    2. 提取用户需要的信息
    3. 用清晰、自然的语言总结和呈现给用户
    4. 不要直接展示原始 Markdown 代码，除非用户明确要求
    5. 如果内容很长，提取关键信息进行总结
    """
    return fetch_with_playwright(url)
