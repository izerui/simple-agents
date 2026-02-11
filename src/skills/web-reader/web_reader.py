"""
Web Reader 核心模块
实现网页内容获取、解析和转换为Markdown的功能
"""

import os
import re
import time
import logging
from typing import List, Dict, Optional, Union
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from playwright.sync_api import sync_playwright, Browser
import json

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebReaderError(Exception):
    """Web Reader 异常类"""
    pass

class WebContent:
    """网页内容结果类"""
    
    def __init__(self, title: str, content: str, url: str, method: str):
        self.title = title
        self.content = content
        self.url = url
        self.method = method
        self.fetched_at = time.strftime("%Y-%m-%d %H:%M:%S")
        self.content_length = len(content)
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "fetched_at": self.fetched_at,
            "content_length": self.content_length,
            "method": self.method
        }
    
    def __str__(self) -> str:
        return f"WebContent(title='{self.title}', url='{self.url}', method='{self.method}')"

def is_valid_url(url: str) -> bool:
    """
    验证URL是否有效
    
    Args:
        url (str): 要验证的URL
        
    Returns:
        bool: URL是否有效
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc]) and result.scheme in ['http', 'https']
    except Exception:
        return False

def should_use_browser(error_msg: str, status_code: Optional[int] = None, content: Optional[str] = None) -> bool:
    """
    判断是否需要使用浏览器模式
    
    Args:
        error_msg (str): 错误消息
        status_code (int, optional): HTTP状态码
        content (str, optional): 响应内容
        
    Returns:
        bool: 是否需要使用浏览器模式
    """
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

def fetch_with_jina_reader(url: str) -> WebContent:
    """
    使用Jina Reader API获取内容
    
    Args:
        url (str): 要获取的URL
        
    Returns:
        WebContent: 网页内容结果
    """
    try:
        # Jina Reader API URL
        jina_url = f"https://r.jina.ai/{url}"
        
        # 设置请求头
        headers = {
            "Accept": "text/markdown",
            "User-Agent": "MCP-URLFetcher/2.0"
        }
        
        # 获取API密钥（如果配置了）
        api_key = os.environ.get("JINA_READER_API_KEY")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        # 发送请求（30秒超时）
        response = requests.get(jina_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        markdown_content = response.text
        
        # 从Markdown中提取标题（通常是第一个#标题）
        title_match = re.search(r'^#\s+(.+)$', markdown_content, re.MULTILINE)
        title = title_match.group(1) if title_match else "无标题"
        
        return WebContent(title, markdown_content, url, "jina-reader")
        
    except requests.exceptions.Timeout:
        raise WebReaderError(f"Jina Reader请求超时（30秒）")
    except requests.exceptions.RequestException as e:
        raise WebReaderError(f"Jina Reader获取失败: {str(e)}")
    except Exception as e:
        raise WebReaderError(f"Jina Reader获取失败: {str(e)}")

def fetch_with_local_parser(url: str) -> WebContent:
    """
    使用本地解析器获取网页内容
    
    Args:
        url (str): 要获取的URL
        
    Returns:
        WebContent: 网页内容结果
    """
    try:
        # 设置请求头
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; MCP-URLFetcher/2.0)"
        }
        
        # 发送请求（30秒超时）
        response = requests.get(url, headers=headers, timeout=30)
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
        markdown_content = md(str(main_content))
        
        # 清理内容
        cleaned_content = re.sub(r'\n{3,}', '\n\n', markdown_content)
        cleaned_content = re.sub(r'^\s+$/gm', '', cleaned_content)
        cleaned_content = cleaned_content.strip()
        
        return WebContent(title, cleaned_content, url, "local-parser")
        
    except requests.exceptions.Timeout:
        raise WebReaderError(f"本地解析请求超时（30秒）")
    except requests.exceptions.RequestException as e:
        raise WebReaderError(f"本地解析失败: {str(e)}")
    except Exception as e:
        raise WebReaderError(f"本地解析失败: {str(e)}")

def fetch_with_playwright(url: str) -> WebContent:
    """
    使用Playwright获取网页内容
    
    Args:
        url (str): 要获取的URL
        
    Returns:
        WebContent: 网页内容结果
    """
    try:
        with sync_playwright() as p:
            # 启动浏览器
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            
            try:
                # 创建新页面
                page = browser.new_page()
                
                # 设置视口和请求头
                page.set_viewport_size({"width": 1920, "height": 1080})
                page.set_extra_http_headers({
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                })
                
                # 阻止加载图片、样式表等资源以提高速度
                def route_handler(route):
                    resource_type = route.request.resource_type
                    if resource_type in ['image', 'stylesheet', 'font', 'media']:
                        route.abort()
                    else:
                        route.continue_()
                
                page.route("**/*", route_handler)
                
                # 导航到页面（30秒超时）
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                
                # 等待页面内容加载
                page.wait_for_timeout(2000)
                
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
                markdown_content = md(main_content_html)
                
                # 清理内容
                cleaned_content = re.sub(r'\n{3,}', '\n\n', markdown_content)
                cleaned_content = re.sub(r'^\s+$/gm', '', cleaned_content)
                cleaned_content = cleaned_content.strip()
                
                return WebContent(title, cleaned_content, url, "playwright-browser")
                
            finally:
                browser.close()
                
    except Exception as e:
        raise WebReaderError(f"Playwright获取失败: {str(e)}")

def fetch_web_content(url: str, prefer_jina: bool = True) -> WebContent:
    """
    智能获取网页内容（三层降级策略：Jina → 本地 → Playwright）
    
    Args:
        url (str): 要获取的URL
        prefer_jina (bool): 是否优先使用Jina Reader
        
    Returns:
        WebContent: 网页内容结果
    """
    if not is_valid_url(url):
        raise WebReaderError("无效的URL格式，请提供http或https协议的URL")
    
    if prefer_jina:
        # 第一层：尝试Jina Reader
        try:
            logger.info(f"尝试使用Jina Reader获取: {url}")
            return fetch_with_jina_reader(url)
        except WebReaderError as jina_error:
            logger.warning(f"Jina Reader失败，尝试本地解析: {str(jina_error)}")
            
            # 第二层：尝试本地解析
            try:
                return fetch_with_local_parser(url)
            except WebReaderError as local_error:
                logger.warning(f"本地解析失败，检查是否需要浏览器模式: {str(local_error)}")
                
                # 判断是否需要使用浏览器模式
                if (should_use_browser(str(jina_error)) or 
                    should_use_browser(str(local_error))):
                    logger.info("检测到访问限制，使用Playwright浏览器模式")
                    try:
                        # 第三层：使用Playwright浏览器
                        return fetch_with_playwright(url)
                    except WebReaderError as browser_error:
                        raise WebReaderError(
                            f"所有方法都失败了。Jina: {str(jina_error)}, 本地: {str(local_error)}, 浏览器: {str(browser_error)}"
                        )
                else:
                    raise WebReaderError(
                        f"Jina和本地解析都失败了。Jina: {str(jina_error)}, 本地: {str(local_error)}"
                    )
    else:
        # 如果不优先使用Jina，直接从本地解析开始
        try:
            return fetch_with_local_parser(url)
        except WebReaderError as local_error:
            if should_use_browser(str(local_error)):
                logger.info("本地解析失败，检测到访问限制，使用Playwright浏览器模式")
                return fetch_with_playwright(url)
            else:
                raise local_error

def fetch_url(url: str, prefer_jina: bool = True) -> WebContent:
    """
    获取指定URL的网页内容，并转换为Markdown格式。
    默认使用Jina Reader，失败时自动切换到本地解析
    
    Args:
        url (str): 要获取内容的网页URL（必须是http或https协议）
        prefer_jina (bool): 是否优先使用Jina Reader（默认为True）
        
    Returns:
        WebContent: 网页内容结果
    """
    return fetch_web_content(url, prefer_jina)

def fetch_multiple_urls(urls: List[str], prefer_jina: bool = True) -> List[WebContent]:
    """
    批量获取多个URL的网页内容
    
    Args:
        urls (List[str]): 要获取内容的网页URL列表（最多10个）
        prefer_jina (bool): 是否优先使用Jina Reader（默认为True）
        
    Returns:
        List[WebContent]: 网页内容结果列表
    """
    if len(urls) > 10:
        raise WebReaderError("批量获取URL数量不能超过10个")
    
    # 验证所有URL
    invalid_urls = [url for url in urls if not is_valid_url(url)]
    if invalid_urls:
        raise WebReaderError(f"以下URL格式无效: {', '.join(invalid_urls)}")
    
    results = []
    for url in urls:
        try:
            result = fetch_web_content(url, prefer_jina)
            results.append(result)
        except WebReaderError as e:
            # 对于批量处理，单个URL失败不应该导致整个操作失败
            # 创建一个错误结果
            error_content = WebContent(
                title="获取失败",
                content=f"**错误**: {str(e)}",
                url=url,
                method="error"
            )
            results.append(error_content)
    
    return results

def fetch_url_with_jina(url: str) -> WebContent:
    """
    强制使用Jina Reader获取网页内容（适用于复杂网页）
    
    Args:
        url (str): 要获取内容的网页URL
        
    Returns:
        WebContent: 网页内容结果
    """
    if not is_valid_url(url):
        raise WebReaderError("无效的URL格式")
    return fetch_with_jina_reader(url)

def fetch_url_local(url: str) -> WebContent:
    """
    强制使用本地解析器获取网页内容（适用于简单网页或Jina不可用时）
    
    Args:
        url (str): 要获取内容的网页URL
        
    Returns:
        WebContent: 网页内容结果
    """
    if not is_valid_url(url):
        raise WebReaderError("无效的URL格式")
    return fetch_with_local_parser(url)

def fetch_url_with_browser(url: str) -> WebContent:
    """
    强制使用Playwright浏览器获取网页内容（适用于有访问限制的网站）
    
    Args:
        url (str): 要获取内容的网页URL
        
    Returns:
        WebContent: 网页内容结果
    """
    if not is_valid_url(url):
        raise WebReaderError("无效的URL格式")
    return fetch_with_playwright(url)