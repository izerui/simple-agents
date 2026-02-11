#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汉斯出版社书目检索服务使用示例（优化版）
"""

import sys
import os

# 添加技能脚本目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from hanspub_retriever_optimized import hanspub_search, get_subject_journals

def example_1_basic_search():
    """示例1: 基本关键词检索"""
    print("=== 示例1: 基本关键词检索 ===")
    
    # 按标题检索"机器学习"
    results = hanspub_search("机器学习", search_field="title", max_results=3)
    
    print(f"找到 {len(results)} 个结果:")
    for i, result in enumerate(results):
        print(f"\n结果 {i+1}:")
        print(f"  标题: {result.get('title', 'N/A')}")
        print(f"  作者: {', '.join(result.get('authors', []))}")
        print(f"  期刊: {result.get('journal', 'N/A')}")

def example_2_medical_search():
    """示例2: 医学领域检索（心内科）"""
    print("\n=== 示例2: 医学领域检索（心内科） ===")
    
    # 获取医药卫生学科下的期刊列表
    medical_journals = get_subject_journals("医药卫生")
    print(f"医药卫生学科包含 {len(medical_journals)} 个期刊:")
    for journal in medical_journals:
        print(f"  - {journal['code']}: {journal['name']}")
    
    # 在亚洲心脑血管病例研究期刊中检索冠心病
    results = hanspub_search("冠心病", journal="ACRVM", max_results=3)
    print(f"\n在ACRVM期刊中找到 {len(results)} 篇冠心病相关文章:")
    for i, result in enumerate(results):
        print(f"\n结果 {i+1}:")
        print(f"  标题: {result.get('title', 'N/A')}")
        print(f"  期刊: {result.get('journal', 'N/A')}")

def example_3_computer_science_search():
    """示例3: 计算机科学检索"""
    print("\n=== 示例3: 计算机科学检索 ===")
    
    # 在计算机科学与应用期刊中检索人工智能
    results = hanspub_search("人工智能", journal="CSA", max_results=3)
    print(f"在CSA期刊中找到 {len(results)} 篇人工智能相关文章:")
    for i, result in enumerate(results):
        print(f"\n结果 {i+1}:")
        print(f"  标题: {result.get('title', 'N/A')}")
        print(f"  作者: {', '.join(result.get('authors', []))}")

if __name__ == "__main__":
    example_1_basic_search()
    example_2_medical_search()
    example_3_computer_science_search()