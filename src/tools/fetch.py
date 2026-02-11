"""
获取网页内容 - 增强反爬虫版本（两层降级策略）
"""
import random
import re
import time
from typing import Any, Optional

import httpx
from httpx import Timeout
from langchain_core.tools import tool
from markdownify import markdownify

# web-reader 相关依赖（需要安装：requests, beautifulsoup4, playwright, playwright-stealth）
WEB_READER_AVAILABLE = True
PLAYWRIGHT_AVAILABLE = True
PLAYWRIGHT_STEALTH_AVAILABLE = False

try:
    import requests
except ImportError:
    WEB_READER_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
except ImportError:
    WEB_READER_AVAILABLE = False

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

try:
    from playwright_stealth import Stealth
    PLAYWRIGHT_STEALTH_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_STEALTH_AVAILABLE = False
    Stealth = None


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
    3. 将其综合成清晰的自然语言响应给用户
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
            "message": f"已经访问{url}，成功将内容转换为Markdown格式并写入到 `markdown_content` 字段内容。",
            "markdown_content": markdown_content,
            "status_code": response.status_code,
            "content_length": len(markdown_content),
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"已经访问{url}，但获取内容时出错。错误信息参考 `error` 字段内容。",
            "error": f"Fetch URL error: {e!s}",
            "url": url
        }


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


def add_random_delay(min_delay: float = 0.5, max_delay: float = 2.0):
    """添加随机延迟，模拟人类行为"""
    delay = random.uniform(min_delay, max_delay)
    time.sleep(delay)


# ==================== Web Reader 工具函数 ====================

def is_valid_url(url: str) -> bool:
    """验证URL是否有效"""
    try:
        from urllib.parse import urlparse
        result = urlparse(url)
        return all([result.scheme, result.netloc]) and result.scheme in ['http', 'https']
    except Exception:
        return False


def should_use_browser(error_msg: str, status_code: Optional[int] = None, content: Optional[str] = None) -> bool:
    """判断是否需要使用浏览器模式"""
    error_lower = error_msg.lower()

    # 基于HTTP状态码判断
    if status_code and status_code in [403, 429, 503, 520, 521, 522, 523, 524]:
        return True

    # 基于错误消息判断
    browser_triggers = [
        'cloudflare', 'access denied', 'forbidden', 'captcha', 'rate limit',
        'robot', 'security', 'blocked', 'protection', 'verification required',
        'too many requests', 'service unavailable'
    ]

    if any(trigger in error_lower for trigger in browser_triggers):
        return True

    # 基于响应内容判断
    if content:
        content_lower = content.lower()
        content_triggers = [
            'cloudflare', 'ray id', 'access denied', 'security check',
            'human verification', 'captcha', 'please verify you are a human'
        ]

        if any(trigger in content_lower for trigger in content_triggers):
            return True

    return False


def fetch_with_local_parser(url: str, use_session: bool = True) -> dict[str, Any]:
    """
    使用本地解析器获取网页内容（增强反爬虫版本）

    Args:
        url: 要获取的URL
        use_session: 是否使用会话（支持Cookie和连接复用）

    Returns:
        包含获取结果的字典
    """
    # 使用会话以支持Cookie和连接复用
    session = requests.Session() if use_session else None

    try:
        # 生成逼真的请求头
        headers = get_realistic_headers(url)

        # 如果使用会话，设置会话级别的默认请求头
        if session:
            session.headers.update(headers)

            # 添加随机延迟，模拟人类行为
            add_random_delay(0.3, 1.0)

            # 发送请求
            response = session.get(url, timeout=30, allow_redirects=True)
        else:
            # 不使用会话，直接发送请求
            response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)

        response.raise_for_status()

        # 获取HTML内容
        html_content = response.text

        # 使用BeautifulSoup解析HTML
        soup = BeautifulSoup(html_content, 'html.parser')

        # 获取标题
        title_tag = soup.find('title')
        title = title_tag.get_text().strip() if title_tag else "无标题"

        # 移除不需要的元素
        elements_to_remove = soup.select('script, style, nav, header, footer, aside, .advertisement, .ads, .sidebar, .comments, .social-share')
        for element in elements_to_remove:
            element.decompose()

        # 获取主要内容区域
        main_content_selectors = [
            'main', 'article', '[role="main"]', '.content', '#content',
            '.post', '.entry-content', 'body'
        ]

        main_content = None
        for selector in main_content_selectors:
            main_content = soup.select_one(selector)
            if main_content:
                break

        if not main_content:
            main_content = soup.body if soup.body else soup

        # 转换为Markdown
        markdown_content = markdownify(str(main_content))

        # 清理内容
        cleaned_content = re.sub(r'\n{3,}', '\n\n', markdown_content)
        cleaned_content = re.sub(r'^\s+$/gm', '', cleaned_content)
        cleaned_content = cleaned_content.strip()

        # 检查内容是否为空（可能是动态加载的页面）
        if not cleaned_content or len(cleaned_content) < 10:
            return {
                "success": False,
                "error": "页面内容为空或过短，可能是动态加载的页面。建议使用浏览器模式（force_method='browser'）重新获取。",
                "url": url,
                "method": "local-parser",
                "suggest_browser": True
            }

        return {
            "success": True,
            "url": url,
            "title": title,
            "markdown_content": cleaned_content,
            "status_code": response.status_code,
            "content_length": len(cleaned_content),
            "method": "local-parser",
            "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "message": f"已经使用本地解析器成功获取 {url} 的内容。"
        }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": "本地解析请求超时（30秒）",
            "url": url,
            "method": "local-parser"
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"本地解析失败: {str(e)}",
            "url": url,
            "method": "local-parser",
            "status_code": getattr(e.response, 'status_code', None) if hasattr(e, 'response') and e.response else None
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"本地解析失败: {str(e)}",
            "url": url,
            "method": "local-parser"
        }
    finally:
        # 关闭会话
        if session:
            session.close()


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
            "url": url,
            "method": "playwright-browser"
        }

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

                # 选择性加载资源（提高速度，但保持一些必要的资源）
                def route_handler(route):
                    resource_type = route.request.resource_type
                    # 阻止图片、字体、媒体（大文件）
                    if resource_type in ['image', 'font', 'media']:
                        route.abort()
                    # 允许其他资源
                    else:
                        route.continue_()

                page.route("**/*", route_handler)

                # 添加随机延迟，模拟人类行为
                add_random_delay(0.2, 0.5)

                # 导航到页面（30秒超时）
                page.goto(url, timeout=30000, wait_until="domcontentloaded")

                # 随机等待时间，模拟人类阅读
                page.wait_for_timeout(random.randint(1500, 3000))

                # 模拟鼠标移动（可选，增加真实性）
                try:
                    page.mouse.move(random.randint(100, 500), random.randint(100, 500))
                except:
                    pass

                # 获取页面标题
                title = page.title() or "无标题"

                # 移除不需要的元素
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
                    "method": "playwright-browser",
                    "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "message": f"已经使用 Playwright 浏览器成功获取 {url} 的内容。"
                }

            finally:
                browser.close()

    except Exception as e:
        return {
            "success": False,
            "error": f"Playwright获取失败: {str(e)}",
            "url": url,
            "method": "playwright-browser"
        }


def fetch_web_content(url: str) -> dict[str, Any]:
    """
    智能获取网页内容（两层降级策略：本地解析 → Playwright 浏览器）

    这是内部函数，实现核心的两层降级逻辑：
    1. 首先尝试本地解析器（快速，资源占用少）
    2. 如果失败且需要浏览器模式，则使用 Playwright

    Args:
        url: 要获取的URL

    Returns:
        包含获取结果的字典
    """
    if not is_valid_url(url):
        return {
            "success": False,
            "error": "无效的URL格式，请提供http或https协议的URL",
            "url": url
        }

    # 第一层：尝试本地解析器（快速，资源占用少）
    local_result = fetch_with_local_parser(url)
    if local_result["success"]:
        return local_result

    # 判断是否需要使用浏览器模式
    # 检查 suggest_browser 标志或错误消息
    need_browser = (
        local_result.get("suggest_browser", False) or
        should_use_browser(local_result.get("error", ""))
    )

    if need_browser:
        # 第二层：使用Playwright浏览器（处理动态页面和反爬）
        browser_result = fetch_with_playwright(url)
        if browser_result["success"]:
            return browser_result
        else:
            return {
                "success": False,
                "error": f"所有方法都失败了。本地: {local_result.get('error')}, 浏览器: {browser_result.get('error')}",
                "url": url
            }
    else:
        # 本地解析失败，且不需要浏览器模式
        return local_result


@tool(parse_docstring=True)
def fetch_url(url: str, force_method: Optional[str] = None) -> dict[str, Any]:
    """获取网页内容并转换为易读的 Markdown 格式。

    这是一个智能网页抓取工具，可以自动处理各种网站，包括有反爬虫保护的网站。
    工具会自动选择最佳方法获取内容，并将结果转换为清晰的 Markdown 格式供你阅读和使用。

    何时使用此工具：
    - 用户要求获取、总结或分析某个网页的内容
    - 需要提取网页中的特定信息（如文章、新闻、数据等）
    - 用户提供的 URL 需要访问并获取内容
    - 需要查看动态加载的页面内容

    工作方式：
    1. 首先尝试快速获取（本地解析器）
    2. 如果遇到反爬虫保护，自动切换到浏览器模式
    3. 自动处理验证码、Cloudflare 保护等

    Args:
        url: 要获取的网页地址（必须是 http:// 或 https:// 开头的有效 URL）
        force_method: 可选参数，强制使用特定方法。可用值：local（本地解析器，快速）、browser（浏览器模式，适合动态页面）

    Returns:
        包含网页信息的字典，主要字段：
        - success: 是否成功获取内容（True/False）
        - markdown_content: 网页内容的 Markdown 格式文本（这是你最需要的字段）
        - title: 网页标题
        - url: 最终访问的 URL
        - method: 使用的方法（local-parser 或 playwright-browser）
        - error: 失败时的错误信息（如果 success 为 False）

    使用指南：
    1. 获取内容后，仔细阅读 markdown_content 字段
    2. 提取用户需要的信息
    3. 用清晰、自然的语言总结和呈现给用户
    4. 不要直接展示原始 Markdown 代码，除非用户明确要求
    5. 如果内容很长，提取关键信息进行总结
    """
    # 检查 web-reader 依赖是否可用
    if not WEB_READER_AVAILABLE:
        return {
            "success": False,
            "error": "Web Reader 功能需要安装依赖：pip install requests beautifulsoup4 playwright",
            "url": url
        }

    try:
        # 如果指fetch_web_content定了强制方法
        if force_method:
            if force_method == 'local':
                return fetch_with_local_parser(url)
            elif force_method == 'browser':
                return fetch_with_playwright(url)
            else:
                return {
                    "success": False,
                    "error": f"无效的强制方法: {force_method}。可选值：'local', 'browser'",
                    "url": url
                }

        # 使用智能降级策略
        return fetch_web_content(url)

    except Exception as e:
        return {
            "success": False,
            "error": f"获取网页内容时发生异常: {str(e)}",
            "url": url
        }
