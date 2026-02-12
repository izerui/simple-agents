"""
获取网页内容 - 使用 Playwright 浏览器模式
"""
import logging
import os
import random
import re
import threading
import time
import uuid
from typing import Any, Optional, cast

logger = logging.getLogger(__name__)

from langchain_core.tools import tool
from markdownify import markdownify

from src.utils.util import get_backend_per_thread

# Playwright 相关依赖
# 注意：以下导入不在文件顶部，因为需要在 try-except 块中处理依赖缺失的情况
# noqa: E402 - 模块级导入不在文件顶部
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


# ==================== 浏览器连接池配置 ====================

# 连接池配置
BROWSER_POOL_SIZE = int(os.getenv('BROWSER_POOL_SIZE', '2'))  # 浏览器池大小
BROWSER_IDLE_TIMEOUT = int(os.getenv('BROWSER_IDLE_TIMEOUT', '300'))  # 闲置超时（秒）
MAX_SCREENSHOT_SIZE = int(os.getenv('MAX_SCREENSHOT_SIZE', '52428800'))  # 最大截图大小（50MB）
BROWSER_POOL_MAX_REUSE = int(os.getenv('BROWSER_POOL_MAX_REUSE', '10'))  # 浏览器实例最大复用次数


class BrowserPool:
        """
        Playwright 浏览器连接池，用于复用浏览器实例以提高性能并减少内存占用。
    
        功能特性：
        - 支持多个浏览器实例的池化管理
        - 自动清理闲置的浏览器实例
        - 限制每个实例的最大复用次数，防止状态污染
        - 线程安全
        - 自动清理资源
        """
    
        def __init__(self, pool_size: int = BROWSER_POOL_SIZE, idle_timeout: int = BROWSER_IDLE_TIMEOUT):
            """初始化浏览器连接池。

            Args:
                pool_size: 池中浏览器实例的最大数量
                idle_timeout: 浏览器实例闲置超时时间（秒）
            """
            import threading
            import queue

            self.pool_size = pool_size
            self.idle_timeout = idle_timeout
            self._playwright = None
            self._browser_queue: queue.Queue = queue.Queue(maxsize=pool_size)
            self._browser_info: dict = {}  # 存储浏览器实例的元信息 {browser_id: info}
            self._lock = threading.Lock()
            self._cleanup_thread = None
            self._running = False
            self._browser_id_counter = 0
            self._playwright_context = None
            self._playwright_lock = threading.Lock()  # 用于保护 Playwright 上下文初始化
    
        def _init_playwright(self):
            """初始化 Playwright 上下文（延迟初始化）。"""
            with self._playwright_lock:
                if self._playwright is not None:
                    return  # 已经初始化过了
                
                if not PLAYWRIGHT_AVAILABLE:
                    raise RuntimeError("Playwright 未安装，无法初始化浏览器池")
            
                # 类型断言：确保 sync_playwright 不是 None
                assert sync_playwright is not None, "sync_playwright should not be None"
                
                self._playwright_context = sync_playwright()
                self._playwright = self._playwright_context.__enter__()
    
        def _create_browser_instance(self):
            """创建新的浏览器实例。

            Returns:
                Browser 实例及其 ID
            """
            # 确保 Playwright 已初始化
            if self._playwright is None:
                self._init_playwright()
            
            # 检查 Playwright 是否成功初始化
            if self._playwright is None:
                raise RuntimeError("Failed to initialize Playwright")
        
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
        
            # 启动浏览器（优化后的参数，减少内存占用）
            browser = self._playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    # 内存管理相关参数
                    '--disable-gpu',
                    '--disable-software-rasterizer',
                    '--disable-extensions',
                    '--disable-background-networking',
                    '--disable-default-apps',
                    '--disable-sync',
                    '--metrics-recording-only',
                    '--no-first-run',
                    '--safebrowsing-disable-auto-update',
                    '--disable-setuid-sandbox',
                    '--disable-logging',
                    '--disable-hang-monitor',
                    '--disable-prompt-on-repost',
                    '--disable-breakpad',
                    '--disable-client-side-phishing-detection',
                    '--disable-component-update',
                    '--disable-domain-reliability',
                ]
            )
        
            # 创建默认上下文
            context = browser.new_context(
                viewport={"width": viewport["width"], "height": viewport["height"]},
                user_agent=user_agent,
                service_workers="block",
                bypass_csp=True
            )
        
            with self._lock:
                self._browser_id_counter += 1
                browser_id = self._browser_id_counter
            
                self._browser_info[browser_id] = {
                    'browser': browser,
                    'context': context,
                    'created_at': time.time(),
                    'last_used': time.time(),
                    'usage_count': 0,
                    'user_agent': user_agent
                }
        
            return context, browser_id
    
        def acquire(self) -> tuple[Any, int]:
            """从池中获取一个浏览器上下文。

            Returns:
                (BrowserContext, browser_id) 元组
            
            Raises:
                RuntimeError: 如果等待超时
            """
            with self._lock:
                current_pool_size = len(self._browser_info)
            
            logger.debug(f"Acquiring browser from pool (current size: {current_pool_size}/{self.pool_size})")
            
            # 尝试从队列中获取可用的浏览器
            browser_id = None
            try:
                browser_id = self._browser_queue.get(block=False)
                logger.debug(f"Got browser {browser_id} from queue")
            except Exception:
                # 队列为空
                logger.debug("Browser queue is empty, will create new instance or wait")
                browser_id = None
            
            # 如果获取到浏览器，验证并返回
            if browser_id is not None:
                with self._lock:
                    info = self._browser_info.get(browser_id)
                
                if not info:
                    # 如果浏览器信息不存在，创建新的
                    logger.warning(f"Browser {browser_id} not found in info dict, creating new instance")
                    return self._create_browser_instance()
            
                # 检查是否超过最大复用次数
                if info['usage_count'] >= BROWSER_POOL_MAX_REUSE:
                    # 关闭旧浏览器
                    logger.info(f"Browser {browser_id} reached max reuse count ({info['usage_count']}), creating new instance")
                    self._close_browser(browser_id)
                    # 创建新的
                    return self._create_browser_instance()
            
                # 更新使用信息
                with self._lock:
                    info['last_used'] = time.time()
                    info['usage_count'] += 1
                
                logger.debug(f"Browser {browser_id} stats: usage_count={info['usage_count']}, idle_time={time.time() - info['last_used']:.2f}s")
            
                # 检查上下文是否仍然有效
                try:
                    # 测试上下文是否可用
                    _ = info['context'].pages[0] if info['context'].pages else None
                    return info['context'], browser_id
                except Exception as e:
                    # 上下文已失效，关闭并创建新的
                    logger.warning(f"Browser {browser_id} context is invalid ({e}), creating new instance")
                    self._close_browser(browser_id)
                    return self._create_browser_instance()
            
            # 队列为空或获取失败，创建新的浏览器或等待
            with self._lock:
                current_pool_size = len(self._browser_info)
            
            if current_pool_size < self.pool_size:
                # 池未满，创建新浏览器
                logger.debug(f"Creating new browser (pool size: {current_pool_size}/{self.pool_size})")
                return self._create_browser_instance()
            else:
                # 池已满，等待可用的浏览器
                logger.debug(f"Pool is full, waiting for available browser")
                try:
                    browser_id = self._browser_queue.get(timeout=30)  # 30秒超时
                    with self._lock:
                        info = self._browser_info.get(browser_id)
                        if info:
                            info['last_used'] = time.time()
                            info['usage_count'] += 1
                            logger.debug(f"Browser {browser_id} acquired after wait")
                            return info['context'], browser_id
                    
                    # 如果信息不存在，创建新的
                    logger.warning(f"Browser {browser_id} not found after wait, creating new instance")
                    return self._create_browser_instance()
                except Exception as timeout_error:
                    logger.error(f"Timeout waiting for available browser: {timeout_error}")
                    raise RuntimeError("Timeout waiting for available browser from pool")
    
        def release(self, browser_id: int):
            """将浏览器上下文归还到池中。

            Args:
                browser_id: 浏览器实例 ID
            """
            if browser_id is None:
                logger.debug("Attempted to release None browser_id")
                return
        
            with self._lock:
                info = self._browser_info.get(browser_id)
                if not info:
                    logger.warning(f"Browser {browser_id} not found in info dict during release")
                    return
            
                info['last_used'] = time.time()
                idle_time = info['last_used'] - info.get('created_at', time.time())
                logger.debug(f"Releasing browser {browser_id} (usage_count: {info['usage_count']}, total_age: {idle_time:.2f}s)")
        
            # 将浏览器 ID 放回队列
            try:
                self._browser_queue.put_nowait(browser_id)
                logger.debug(f"Browser {browser_id} returned to pool")
            except Exception as e:
                # 队列已满，关闭这个浏览器
                logger.warning(f"Queue full when releasing browser {browser_id}, closing it: {e}")
                self._close_browser(browser_id)
    
        def _close_browser(self, browser_id: int):
            """关闭指定的浏览器实例。

            Args:
                browser_id: 浏览器实例 ID
            """
            with self._lock:
                info = self._browser_info.pop(browser_id, None)
                if not info:
                    logger.debug(f"Browser {browser_id} not found for closing")
                    return
            
            logger.info(f"Closing browser {browser_id} (usage_count: {info['usage_count']}, age: {time.time() - info['created_at']:.2f}s)")
            
            try:
                # 关闭所有页面
                page_count = 0
                for page in info['context'].pages:
                    try:
                        page.close()
                        page_count += 1
                    except Exception as e:
                        logger.warning(f"Error closing page in browser {browser_id}: {e}")
                
                logger.debug(f"Closed {page_count} pages for browser {browser_id}")
            
                # 关闭上下文
                try:
                    info['context'].close()
                except Exception as e:
                    logger.warning(f"Error closing context for browser {browser_id}: {e}")
            
                # 关闭浏览器
                try:
                    info['browser'].close()
                except Exception as e:
                    logger.warning(f"Error closing browser {browser_id}: {e}")
            except Exception as e:
                logger.error(f"Error closing browser instance {browser_id}: {e}", exc_info=True)
    
        def cleanup_idle_browsers(self):
            """清理闲置超时的浏览器实例。"""
            browsers_to_close = []
            
            with self._lock:
                current_time = time.time()
                
                for browser_id, info in list(self._browser_info.items()):
                    idle_time = current_time - info['last_used']
                    if idle_time > self.idle_timeout:
                        browsers_to_close.append((browser_id, idle_time))
            
            if browsers_to_close:
                logger.info(f"Cleaning up {len(browsers_to_close)} idle browsers")
                
                # 在锁外关闭浏览器，避免阻塞其他操作
                for browser_id, idle_time in browsers_to_close:
                    logger.debug(f"Closing idle browser {browser_id} (idle for {idle_time:.2f}s)")
                    self._close_browser(browser_id)
                    
                    # 从队列中移除（如果存在）
                    try:
                        # 创建一个临时队列来移除特定的 ID
                        temp_queue = []
                        while not self._browser_queue.empty():
                            try:
                                bid = self._browser_queue.get_nowait()
                                if bid != browser_id:
                                    temp_queue.append(bid)
                            except Exception:
                                break
                        # 将其他 ID 放回队列
                        for bid in temp_queue:
                            try:
                                self._browser_queue.put_nowait(bid)
                            except Exception:
                                break
                    except Exception as e:
                        logger.warning(f"Error removing browser {browser_id} from queue: {e}")
    
        def start_cleanup_thread(self):
            """启动后台清理线程。"""
            if self._cleanup_thread and self._cleanup_thread.is_alive():
                return
        
            import threading
        
            def cleanup_loop():
                while self._running:
                    import time
                    time.sleep(60)  # 每分钟检查一次
                    self.cleanup_idle_browsers()
        
            self._running = True
            self._cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
            self._cleanup_thread.start()
    
        def stop_cleanup_thread(self):
            """停止后台清理线程。"""
            self._running = False
            if self._cleanup_thread:
                self._cleanup_thread.join(timeout=5)
                self._cleanup_thread = None
    
        def close_all(self):
            """关闭所有浏览器实例并清理资源。"""
            self.stop_cleanup_thread()
        
            with self._lock:
                # 关闭所有浏览器
                for browser_id in list(self._browser_info.keys()):
                    self._close_browser(browser_id)
            
            # 清空队列
            while not self._browser_queue.empty():
                try:
                    self._browser_queue.get_nowait()
                except Exception:
                    break
        
            # 关闭 Playwright 上下文（需要在锁外进行，因为可能会阻塞）
            playwright_context = None
            with self._lock:
                if self._playwright_context:
                    playwright_context = self._playwright_context
                    self._playwright_context = None
                    self._playwright = None
            
            if playwright_context:
                try:
                    playwright_context.__exit__(None, None, None)
                except Exception:
                    pass
    
        def get_status(self) -> dict[str, Any]:
            """获取浏览器池的状态信息。

            Returns:
                包含池状态信息的字典
            """
            with self._lock:
                current_time = time.time()
                
                active_browsers = 0
                idle_browsers = 0
                total_usage_count = 0
                ages = []
                idle_times = []
                
                for browser_id, info in self._browser_info.items():
                    total_usage_count += info['usage_count']
                    age = current_time - info['created_at']
                    idle_time = current_time - info['last_used']
                    
                    ages.append(age)
                    idle_times.append(idle_time)
                    
                    if idle_time < 10:  # 10秒内使用过的认为是活跃的
                        active_browsers += 1
                    else:
                        idle_browsers += 1
                
                return {
                    'pool_size': self.pool_size,
                    'total_browsers': len(self._browser_info),
                    'active_browsers': active_browsers,
                    'idle_browsers': idle_browsers,
                    'queue_size': self._browser_queue.qsize(),
                    'total_usage_count': total_usage_count,
                    'average_age': sum(ages) / len(ages) if ages else 0,
                    'average_idle_time': sum(idle_times) / len(idle_times) if idle_times else 0,
                    'max_idle_time': max(idle_times) if idle_times else 0,
                    'cleanup_thread_running': self._cleanup_thread.is_alive() if self._cleanup_thread else False,
                }
    
        def get_statistics(self) -> dict[str, Any]:
            """获取浏览器池的详细统计信息。

            Returns:
                包含详细统计信息的字典
            """
            with self._lock:
                current_time = time.time()
                
                browser_details = []
                for browser_id, info in self._browser_info.items():
                    browser_details.append({
                        'browser_id': browser_id,
                        'age_seconds': current_time - info['created_at'],
                        'idle_seconds': current_time - info['last_used'],
                        'usage_count': info['usage_count'],
                        'user_agent': info['user_agent'],
                    })
                
                # 按空闲时间排序
                browser_details.sort(key=lambda x: x['idle_seconds'], reverse=True)
            
            return {
                'status': self.get_status(),
                'browser_details': browser_details,
            }
    
        def health_check(self) -> tuple[bool, str]:
            """检查浏览器池的健康状态。

            Returns:
                (是否健康, 健康状态描述)
            """
            try:
                status = self.get_status()
                
                # 检查是否有浏览器实例
                if status['total_browsers'] == 0:
                    return False, "No browser instances available"
                
                # 检查清理线程是否运行
                if not status['cleanup_thread_running'] and self._running:
                    return False, "Cleanup thread not running"
                
                # 检查是否有卡死的浏览器（空闲时间过长）
                if status['max_idle_time'] > self.idle_timeout * 2:
                    return False, f"Stale browser detected (idle for {status['max_idle_time']:.0f}s)"
                
                # 检查队列是否正常
                if status['queue_size'] > self.pool_size:
                    return False, f"Queue size ({status['queue_size']}) exceeds pool size ({self.pool_size})"
                
                return True, "Browser pool is healthy"
            
            except Exception as e:
                logger.error(f"Health check failed: {e}", exc_info=True)
                return False, f"Health check failed: {str(e)}"
    
        def __del__(self):
            """析构函数，确保资源被清理。"""
            self.close_all()


# 全局浏览器池实例
_global_browser_pool: Optional[BrowserPool] = None
_browser_pool_lock = threading.Lock()


def get_global_browser_pool() -> BrowserPool:
    """获取全局浏览器池实例（单例模式）。

    Returns:
        BrowserPool 实例
    """
    global _global_browser_pool

    if _global_browser_pool is None:
        with _browser_pool_lock:
            if _global_browser_pool is None:
                _global_browser_pool = BrowserPool()
                _global_browser_pool.start_cleanup_thread()

    return _global_browser_pool


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
    使用Playwright获取网页内容（增强反爬虫版本 + playwright-stealth + 浏览器连接池）

    模拟真实浏览器行为，包括：
    - 随机视口大小
    - 逼真的User-Agent
    - 完整的浏览器指纹（使用 playwright-stealth）
    - 模拟人类操作延迟
    - 使用浏览器连接池提高性能
    - 智能截图大小控制
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
    
    # 获取浏览器池
    browser_pool = get_global_browser_pool()
    
    context = None
    page = None
    browser_id = None
    stealth = None  # 保存 stealth 引用，用于后续清理
    screenshot_filename = None

    try:
        # 从浏览器池获取上下文
        context, browser_id = browser_pool.acquire()
        
        # 在上下文中创建新页面
        # 使用 cast 告诉类型检查器 context 不是 None
        page = cast(Any, context).new_page()

        # 使用 playwright-stealth 隐藏浏览器指纹
        if PLAYWRIGHT_STEALTH_AVAILABLE:
            stealth = Stealth()  # type: ignore - PLAYWRIGHT_STEALTH_AVAILABLE 已在运行时检查
            stealth.apply_stealth_sync(page)
        else:
            stealth = None

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

        # 智能截图：控制截图大小
        screenshot_uuid = str(uuid.uuid4())
        screenshot_filename = f".capture/{screenshot_uuid}.png"
        screenshot_path = backend._resolve_path(screenshot_filename)
        
        # 先尝试全页截图
        screenshot_bytes = page.screenshot(full_page=True)
        
        # 如果截图太大，降级为只截图可视区域
        if len(screenshot_bytes) > MAX_SCREENSHOT_SIZE:
            import logging
            logging.warning(
                f"页面截图过大 ({len(screenshot_bytes)} bytes > {MAX_SCREENSHOT_SIZE}), "
                f"降级为可视区域截图"
            )
            screenshot_bytes = page.screenshot(full_page=False)
        
        # 保存截图
        with open(screenshot_path, 'wb') as f:
            f.write(screenshot_bytes)
        
        # 立即释放大对象，避免内存泄漏
        del screenshot_bytes
        screenshot_bytes = None  # noqa: F841 - 有意设置为 None 以帮助垃圾回收

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

    except Exception as e:
        return {
            "success": False,
            "error": f"Playwright获取失败: {str(e)}",
            "url": url
        }
    
    finally:
        # 清理页面资源
        if page is not None:
            try:
                page.close()
            except Exception:
                pass
        
        # 清理 stealth 对象（可能持有对 page 的引用）
        if stealth is not None:
            try:
                del stealth
            except Exception:
                pass
        
        # 将浏览器上下文归还到池中
        if browser_id is not None:
            browser_pool.release(browser_id)


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
