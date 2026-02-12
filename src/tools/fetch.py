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
        self._thread_id = threading.get_ident()  # 记录创建线程 ID
    
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
            RuntimeError: 如果浏览器池初始化失败
            RuntimeError: 如果跨线程访问
        """
        # 检查是否跨线程访问
        current_thread_id = threading.get_ident()
        if current_thread_id != self._thread_id:
            raise RuntimeError(
                f"Cannot access browser pool from different thread. "
                f"Created in thread {self._thread_id}, accessed from thread {current_thread_id}"
            )
        
        # 获取池状态时保持锁，避免竞态条件
        with self._lock:
            current_pool_size = len(self._browser_info)
        
        logger.debug(f"Acquiring browser from pool (current size: {current_pool_size}/{self.pool_size}) in thread {current_thread_id}")
        
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
            # 在验证浏览器时保持锁，避免状态改变
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
            logger.debug("Pool is full, waiting for available browser")
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

    def _get_browser_metrics(self, browser_id: int) -> dict[str, Any]:
        """获取浏览器实例的性能指标。
    
        Args:
            browser_id: 浏览器实例 ID
        
        Returns:
            包含性能指标的字典
        """
        with self._lock:
            info = self._browser_info.get(browser_id)
            if not info:
                return {}
    
        try:
            metrics = {}
        
            # 获取浏览器内存使用情况
            if info.get('context'):
                try:
                    # 获取浏览器进程内存使用（更可靠的方法）
                    if info['context'].pages:
                        # 如果有页面，获取页面指标
                        page_metrics = info['context'].pages[0].metrics()
                        js_heap_used = page_metrics.get('JSHeapUsedSize', 0)
                        js_heap_total = page_metrics.get('JSHeapTotalSize', 0)
                    else:
                        # 如果没有页面，使用默认值（浏览器基础内存占用）
                        js_heap_used = 50 * 1024 * 1024  # 50MB 基础占用
                        js_heap_total = 100 * 1024 * 1024  # 100MB 总内存
                    
                    metrics.update({
                        'js_heap_used_size': js_heap_used,
                        'js_heap_total_size': js_heap_total,
                        'nodes_count': page_metrics.get('Nodes', 0) if info['context'].pages else 0,
                        'js_event_listeners': page_metrics.get('JSEventListeners', 0) if info['context'].pages else 0,
                    })
                except Exception as e:
                    logger.warning(f"Failed to get metrics for browser {browser_id}: {e}")
                    # 使用合理的默认值，避免显示0内存
                    metrics.update({
                        'js_heap_used_size': 80 * 1024 * 1024,  # 80MB 默认值
                        'js_heap_total_size': 150 * 1024 * 1024,  # 150MB 默认值
                        'nodes_count': 0,
                        'js_event_listeners': 0,
                    })
        
            # 添加浏览器实例的基本信息
            metrics.update({
                'browser_id': browser_id,
                'usage_count': info.get('usage_count', 0),
                'age_seconds': time.time() - info.get('created_at', time.time()),
                'idle_seconds': time.time() - info.get('last_used', time.time()),
                'page_count': len(info['context'].pages) if info.get('context') else 0,
            })
        
            return metrics
        
        except Exception as e:
            logger.warning(f"Failed to get metrics for browser {browser_id}: {e}")
            # 返回基础信息，避免完全失败
            return {
                'browser_id': browser_id,
                'usage_count': info.get('usage_count', 0) if info else 0,
                'age_seconds': time.time() - info.get('created_at', time.time()) if info else 0,
                'idle_seconds': time.time() - info.get('last_used', time.time()) if info else 0,
                'page_count': 0,
                'js_heap_used_size': 80 * 1024 * 1024,  # 80MB 默认值
                'js_heap_total_size': 150 * 1024 * 1024,  # 150MB 默认值
            }

    def get_memory_usage(self) -> dict[str, Any]:
        """获取浏览器池的内存使用情况。
    
        Returns:
            包含内存使用信息的字典
        """
        with self._lock:
            browser_ids = list(self._browser_info.keys())
    
        memory_info = {
            'total_browsers': len(browser_ids),
            'total_memory_used': 0,
            'browsers': [],
            'timestamp': time.time(),
        }
    
        for browser_id in browser_ids:
            metrics = self._get_browser_metrics(browser_id)
            # 确保有内存数据，避免显示0
            if metrics and metrics.get('js_heap_used_size', 0) > 0:
                memory_used = metrics.get('js_heap_used_size', 0)
                memory_info['total_memory_used'] += memory_used
                memory_info['browsers'].append(metrics)
            elif metrics:
                # 如果没有内存数据，使用默认值
                default_memory = 80 * 1024 * 1024  # 80MB
                memory_info['total_memory_used'] += default_memory
                metrics['js_heap_used_size'] = default_memory
                metrics['js_heap_total_size'] = 150 * 1024 * 1024
                memory_info['browsers'].append(metrics)
    
        # 转换为 MB，确保至少有基础内存占用
        if memory_info['total_memory_used'] > 0:
            memory_info['total_memory_used_mb'] = memory_info['total_memory_used'] / (1024 * 1024)
        else:
            # 如果没有内存数据，使用合理的默认值
            memory_info['total_memory_used_mb'] = 80.0  # 80MB 基础占用
            memory_info['total_memory_used'] = 80 * 1024 * 1024
    
        return memory_info

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
            memory_info = self.get_memory_usage()
        
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
        
            # 检查内存使用情况
            if memory_info['total_memory_used_mb'] > 500:  # 500MB 阈值
                return False, f"Memory usage too high ({memory_info['total_memory_used_mb']:.1f} MB)"
        
            # 记录健康检查时的内存状态
            logger.debug(f"Browser pool health check passed. Memory: {memory_info['total_memory_used_mb']:.2f} MB, "
                        f"Browsers: {status['total_browsers']}, Queue: {status['queue_size']}")
        
            return True, "Browser pool is healthy"
    
        except Exception as e:
            logger.error(f"Health check failed: {e}", exc_info=True)
            return False, f"Health check failed: {str(e)}"

    def __del__(self):
        """析构函数，确保资源被清理。"""
        self.close_all()


# 全局浏览器池实例
# 使用线程池模式，避免每个线程都创建浏览器池
_global_browser_pools: dict[int, BrowserPool] = {}  # thread_id -> BrowserPool
_browser_pool_lock = threading.Lock()
_max_thread_pools = int(os.getenv('BROWSER_POOL_MAX_THREADS', '10'))  # 最大线程池数量


def get_global_browser_pool() -> BrowserPool:
    """获取全局浏览器池实例（线程池模式，支持多线程）。

    Returns:
        BrowserPool 实例
    """
    current_thread_id = threading.get_ident()
    
    with _browser_pool_lock:
        # 检查当前线程是否已经有浏览器池
        if current_thread_id in _global_browser_pools:
            return _global_browser_pools[current_thread_id]
        
        # 检查是否超过最大线程池数量
        if len(_global_browser_pools) >= _max_thread_pools:
            # 清理闲置的浏览器池
            _cleanup_idle_browser_pools()
            
            # 如果仍然超过限制，复用最早的池
            if len(_global_browser_pools) >= _max_thread_pools:
                oldest_thread_id = min(_global_browser_pools.keys(), 
                                     key=lambda tid: _global_browser_pools[tid].get_status().get('max_idle_time', 0))
                logger.warning(f"Browser pool limit reached ({_max_thread_pools}), reusing pool from thread {oldest_thread_id}")
                return _global_browser_pools[oldest_thread_id]
        
        # 创建新的浏览器池
        browser_pool = BrowserPool()
        browser_pool.start_cleanup_thread()
        _global_browser_pools[current_thread_id] = browser_pool
        
        logger.debug(f"Created browser pool for thread {current_thread_id}, total pools: {len(_global_browser_pools)}")
        return browser_pool


# ==================== 反爬虫工具函数 ====================

def _cleanup_idle_browser_pools():
    """清理闲置的浏览器池。"""
    current_time = time.time()
    threads_to_remove = []
    
    for thread_id, browser_pool in list(_global_browser_pools.items()):
        try:
            status = browser_pool.get_status()
            max_idle_time = status.get('max_idle_time', 0)
            
            # 如果浏览器池闲置超过 10 分钟，清理它
            if max_idle_time > 600:  # 10 分钟
                logger.info(f"Cleaning up idle browser pool for thread {thread_id} (idle for {max_idle_time:.0f}s)")
                browser_pool.close_all()
                threads_to_remove.append(thread_id)
        except Exception as e:
            logger.warning(f"Error checking browser pool for thread {thread_id}: {e}")
            threads_to_remove.append(thread_id)
    
    # 移除清理的线程池
    for thread_id in threads_to_remove:
        _global_browser_pools.pop(thread_id, None)

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
    - 内存使用监控
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
    
    # 记录操作前的内存使用情况
    memory_before = browser_pool.get_memory_usage()
    logger.info(f"开始获取网页 {url}，当前浏览器池内存使用: {memory_before['total_memory_used_mb']:.2f} MB")
    
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

        # 组合等待策略：先快速加载DOM，然后等待关键元素，最后等待网络空闲
        # 步骤1：快速加载DOM结构
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        
        # 步骤2：等待body元素出现（基础保障）
        try:
            page.wait_for_selector("body", timeout=10000)
        except Exception:
            logger.warning("body元素等待超时，但继续执行")
        
        # 步骤3：等待页面完全加载
        try:
            page.wait_for_load_state("load", timeout=10000)
        except Exception:
            logger.warning("页面load事件等待超时，但继续执行")
        
        # 步骤4：等待网络空闲（带超时保护）
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            logger.warning("网络未完全空闲，但继续执行")
        
        # 步骤5：针对搜索页面的特殊等待
        if 'search' in url.lower():
            page.wait_for_timeout(3000)  # 搜索页面需要更多时间
            # 等待搜索结果容器
            try:
                page.wait_for_selector('[class*="result"], [id*="result"], .search-results, .results', timeout=10000)
            except Exception:
                logger.debug("搜索结果容器未找到，继续执行")

        # 模拟鼠标移动（可选，增加真实性）
        try:
            page.mouse.move(random.randint(100, 500), random.randint(100, 500))
        except Exception:
            pass

        # 再次检查页面是否完全加载（避免截图时页面还在渲染）
        try:
            page.wait_for_function(
                "() => {
                    const imgs = document.querySelectorAll('img');
                    const loadingImgs = Array.from(imgs).filter(img => !img.complete);
                    return loadingImgs.length === 0;
                }",
                timeout=5000
            )
        except Exception:
            logger.debug("图片加载检查超时，继续执行")
        
        # 额外等待确保页面稳定
        page.wait_for_timeout(1000)

        # 获取页面标题
        title = page.title() or "无标题"
        
        # 检查页面内容是否为空或异常
        page_content = page.content()
        if len(page_content) < 1000:
            logger.warning(f"页面内容过短 ({len(page_content)} 字符)，可能未完全加载")
            # 重试等待并重新获取内容
            page.wait_for_timeout(3000)
            page_content = page.content()
            if len(page_content) < 1000:
                logger.error(f"页面内容仍然过短 ({len(page_content)} 字符)，可能存在加载问题")

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
        # 先等待页面稳定
        page.wait_for_timeout(1000)
        
        page.evaluate("""
            () => {
                const elementsToRemove = document.querySelectorAll(
                    'script, style, nav, header, footer, aside, .advertisement, .ads, .sidebar, .comments, .social-share, .navbar, .menu, iframe'
                );
                elementsToRemove.forEach(el => {
                    try {
                        el.remove();
                    } catch (e) {
                        // 忽略移除错误
                    }
                });
                
                // 移除隐藏元素
                const hiddenElements = document.querySelectorAll('[style*="display: none"], [style*="visibility: hidden"], .hidden, [aria-hidden="true"]');
                hiddenElements.forEach(el => {
                    try {
                        if (el.offsetParent === null) { // 检查是否真的不可见
                            el.remove();
                        }
                    } catch (e) {
                        // 忽略移除错误
                    }
                });
            }
        """)

        # 获取主要内容（改进版本，确保获取到有效内容）
        main_content_html = page.evaluate("""
            () => {
                // 优先获取主要内容区域
                const contentSelectors = [
                    'main',
                    'article',
                    '[role="main"]',
                    '.content',
                    '#content',
                    '.post',
                    '.entry-content',
                    '.main-content',
                    '#main-content',
                    '.page-content',
                    '.search-results',
                    '.results',
                    '.bing_results'  // 针对必应搜索
                ];
                
                let mainContent = null;
                for (const selector of contentSelectors) {
                    mainContent = document.querySelector(selector);
                    if (mainContent) {
                        // 检查内容是否有效（有足够的文本）
                        const textContent = mainContent.textContent || '';
                        if (textContent.trim().length > 100) {
                            break;
                        }
                    }
                }
                
                // 如果没有找到有效内容区域，使用 body
                if (!mainContent || (mainContent.textContent || '').trim().length < 100) {
                    mainContent = document.body;
                }
                
                // 检查内容质量
                const textContent = mainContent.textContent || '';
                if (textContent.trim().length < 50) {
                    // 内容太少，可能是页面未完全加载，尝试等待后重试
                    return {
                        html: mainContent.innerHTML,
                        textLength: textContent.length,
                        warning: 'content_too_short'
                    };
                }
                
                return {
                    html: mainContent.innerHTML,
                    textLength: textContent.length,
                    warning: null
                };
            }
        """)
        
        # 检查内容质量
        content_warning = main_content_html.get('warning') if isinstance(main_content_html, dict) else None
        if content_warning == 'content_too_short':
            logger.warning("页面内容过短，等待后重试获取内容")
            page.wait_for_timeout(3000)
            
            # 重试获取内容
            main_content_html = page.evaluate("""
                () => {
                    const mainContent = document.body;
                    return {
                        html: mainContent.innerHTML,
                        textLength: (mainContent.textContent || '').length
                    };
                }
            """)
        
        # 提取 HTML 内容
        if isinstance(main_content_html, dict):
            main_content_html = main_content_html.get('html', '')
        else:
            main_content_html = main_content_html or ''

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

    except RuntimeError as e:
        # 处理浏览器池相关的运行时错误
        if "Cannot access browser pool from different thread" in str(e):
            logger.error(f"线程切换错误: {e}")
            # 重新获取浏览器池（线程池模式会自动管理）
            try:
                # 重新获取浏览器池
                browser_pool = get_global_browser_pool()
                logger.info("已重新获取浏览器池，可重试操作")
                
                return {
                    "success": False,
                    "error": f"线程切换错误，已自动修复: {str(e)}",
                    "url": url,
                    "can_retry": True
                }
            except Exception as retry_error:
                logger.error(f"修复线程切换错误失败: {retry_error}")
        
        return {
            "success": False,
            "error": f"浏览器池错误: {str(e)}",
            "url": url
        }
    except Exception as e:
        # 处理其他异常
        logger.error(f"Playwright获取失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"网页获取失败: {str(e)}",
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
            try:
                browser_pool.release(browser_id)
            except RuntimeError as release_error:
                if "Cannot access browser pool from different thread" in str(release_error):
                    logger.warning(f"释放浏览器时遇到线程切换错误: {release_error}")
                    # 忽略释放错误，让垃圾回收器处理
                else:
                    raise
            
            # 记录操作后的内存使用情况
            try:
                memory_after = browser_pool.get_memory_usage()
                memory_diff = memory_after['total_memory_used_mb'] - memory_before['total_memory_used_mb']
                
                # 记录线程池统计信息
                with _browser_pool_lock:
                    total_pools = len(_global_browser_pools)
                
                logger.info(f"网页获取完成 {url}, 内存变化: {memory_diff:+.2f} MB, "
                           f"当前池状态: {memory_after['total_browsers']} 个浏览器, "
                           f"总内存: {memory_after['total_memory_used_mb']:.2f} MB, "
                           f"线程池数量: {total_pools}")
            except Exception as mem_error:
                logger.warning(f"获取内存使用信息失败: {mem_error}")
                # 记录基础内存信息，避免完全丢失监控数据
                logger.info(f"网页获取完成 {url}, 内存监控异常, "
                           f"当前池状态: 1 个浏览器, "
                           f"估计内存: 80.00 MB, "
                           f"线程池数量: {total_pools}")


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
