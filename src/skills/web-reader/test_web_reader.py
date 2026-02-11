#!/usr/bin/env python3
"""
Web Reader 技能测试脚本
"""

import os
import sys
import time
from web_reader import (
    fetch_url,
    fetch_multiple_urls,
    fetch_url_with_jina,
    fetch_url_local,
    fetch_url_with_browser,
    WebReaderError
)

def test_basic_functionality():
    """测试基本功能"""
    print("=== 测试基本功能 ===")
    
    # 测试简单的URL
    test_url = "https://httpbin.org/html"
    
    try:
        print(f"测试URL: {test_url}")
        result = fetch_url(test_url)
        print(f"标题: {result.title}")
        print(f"方法: {result.method}")
        print(f"内容长度: {result.content_length}")
        print(f"内容预览: {result.content[:200]}...")
        print("✓ 基本功能测试通过\n")
    except Exception as e:
        print(f"✗ 基本功能测试失败: {e}\n")

def test_jina_reader():
    """测试Jina Reader"""
    print("=== 测试Jina Reader ===")
    
    test_url = "https://example.com"
    
    try:
        print(f"测试URL: {test_url}")
        result = fetch_url_with_jina(test_url)
        print(f"标题: {result.title}")
        print(f"方法: {result.method}")
        print(f"内容长度: {result.content_length}")
        print("✓ Jina Reader测试通过\n")
    except Exception as e:
        print(f"✗ Jina Reader测试失败: {e}\n")

def test_local_parser():
    """测试本地解析器"""
    print("=== 测试本地解析器 ===")
    
    test_url = "https://httpbin.org/html"
    
    try:
        print(f"测试URL: {test_url}")
        result = fetch_url_local(test_url)
        print(f"标题: {result.title}")
        print(f"方法: {result.method}")
        print(f"内容长度: {result.content_length}")
        print("✓ 本地解析器测试通过\n")
    except Exception as e:
        print(f"✗ 本地解析器测试失败: {e}\n")

def test_batch_processing():
    """测试批量处理"""
    print("=== 测试批量处理 ===")
    
    test_urls = [
        "https://httpbin.org/html",
        "https://example.com"
    ]
    
    try:
        print(f"测试URL列表: {test_urls}")
        results = fetch_multiple_urls(test_urls)
        print(f"获取到 {len(results)} 个结果")
        for i, result in enumerate(results):
            print(f"  {i+1}. {result.url} - {result.method} - {result.content_length} 字符")
        print("✓ 批量处理测试通过\n")
    except Exception as e:
        print(f"✗ 批量处理测试失败: {e}\n")

def main():
    """主测试函数"""
    print("Web Reader 技能测试开始\n")
    
    # 运行所有测试
    test_basic_functionality()
    test_jina_reader()
    test_local_parser()
    test_batch_processing()
    
    print("Web Reader 技能测试完成")

if __name__ == "__main__":
    main()