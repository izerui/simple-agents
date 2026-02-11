#!/usr/bin/env python3
"""
Web Reader 技能使用示例
"""

from web_reader import (
    fetch_url,
    fetch_multiple_urls,
    fetch_url_with_jina,
    fetch_url_local,
    fetch_url_with_browser
)

def example_1_smart_fetch():
    """示例1: 智能获取（推荐方式）"""
    print("=== 示例1: 智能获取 ===")
    
    # 自动选择最佳方法获取内容
    url = "https://example.com"
    result = fetch_url(url)
    
    print(f"标题: {result.title}")
    print(f"URL: {result.url}")
    print(f"使用方法: {result.method}")
    print(f"获取时间: {result.fetched_at}")
    print(f"内容长度: {result.content_length} 字符")
    print(f"内容预览:\n{result.content[:300]}...\n")

def example_2_batch_fetch():
    """示例2: 批量获取"""
    print("=== 示例2: 批量获取 ===")
    
    urls = [
        "https://example.com",
        "https://httpbin.org/html"
    ]
    
    results = fetch_multiple_urls(urls)
    
    for i, result in enumerate(results, 1):
        print(f"结果 {i}:")
        print(f"  URL: {result.url}")
        print(f"  标题: {result.title}")
        print(f"  方法: {result.method}")
        print(f"  内容长度: {result.content_length} 字符")
        print()

def example_3_force_jina():
    """示例3: 强制使用Jina Reader"""
    print("=== 示例3: 强制使用Jina Reader ===")
    
    url = "https://example.com"
    result = fetch_url_with_jina(url)
    
    print(f"标题: {result.title}")
    print(f"使用Jina Reader获取成功!")
    print(f"内容预览:\n{result.content[:200]}...\n")

def example_4_force_browser():
    """示例4: 强制使用浏览器模式"""
    print("=== 示例4: 强制使用浏览器模式 ===")
    
    # 对于有访问限制的网站，直接使用浏览器模式
    url = "https://example.com"
    result = fetch_url_with_browser(url)
    
    print(f"标题: {result.title}")
    print(f"使用Playwright浏览器获取成功!")
    print(f"内容预览:\n{result.content[:200]}...\n")

def example_5_error_handling():
    """示例5: 错误处理"""
    print("=== 示例5: 错误处理 ===")
    
    from web_reader import WebReaderError
    
    try:
        # 尝试获取无效URL
        result = fetch_url("invalid-url")
    except WebReaderError as e:
        print(f"捕获到WebReaderError: {e}")
    
    try:
        # 尝试获取不存在的URL
        result = fetch_url("https://this-domain-does-not-exist-12345.com")
    except WebReaderError as e:
        print(f"捕获到网络错误: {e}")

if __name__ == "__main__":
    print("Web Reader 技能使用示例\n")
    
    # 运行所有示例
    example_1_smart_fetch()
    example_2_batch_fetch()
    example_3_force_jina()
    example_4_force_browser()
    example_5_error_handling()
    
    print("所有示例执行完成!")