#!/usr/bin/env python3
"""
批量AI检测工具
Batch AI Detection Tool

快速批量检测多个文件或多个文本段的AI率
适用于论文各章节分别检测
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Dict
from comprehensive_detector import ComprehensiveAIDetector


def batch_detect_files(file_paths: List[str], output_file: str = None) -> List[Dict]:
    """
    批量检测文件

    Args:
        file_paths: 文件路径列表
        output_file: 输出JSON文件路径（可选）

    Returns:
        检测结果列表
    """
    detector = ComprehensiveAIDetector()
    results = []

    for file_path in file_paths:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()

            if len(text.strip()) < 100:
                print(f"跳过 {file_path}: 文本太短")
                continue

            print(f"正在检测: {file_path}")
            result = detector.detect(text)

            results.append({
                'file': file_path,
                'result': result
            })

            print(f"  风险等级: {result['risk_level']}")
            print(f"  AI概率: {result['overall_score']:.1%}\n")

        except Exception as e:
            print(f"错误 {file_path}: {e}")

    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存到: {output_file}")

    return results


def detect_chapters(text: str, chapter_names: List[str] = None) -> Dict:
    """
    按章节检测论文

    Args:
        text: 论文全文
        chapter_names: 章节名称列表（可选）

    Returns:
        各章节检测结果
    """
    import re

    detector = ComprehensiveAIDetector()

    # 默认章节划分
    if chapter_names is None:
        chapter_names = [
            '摘要',
            '第一章',
            '第二章',
            '第三章',
            '第四章',
            '结论',
            '参考文献'
        ]

    # 按章节分割
    chapters = {}
    current_chapter = None
    current_content = []

    lines = text.split('\n')
    for line in lines:
        # 检测章节标题
        is_chapter = False
        for chapter in chapter_names:
            if chapter in line:
                if current_chapter:
                    chapters[current_chapter] = '\n'.join(current_content)
                current_chapter = chapter
                current_content = []
                is_chapter = True
                break

        if not is_chapter and current_chapter:
            current_content.append(line)

    if current_chapter and current_content:
        chapters[current_chapter] = '\n'.join(current_content)

    # 检测各章节
    results = {}
    for chapter, content in chapters.items():
        if len(content.strip()) > 100:
            print(f"检测章节: {chapter}")
            result = detector.detect(content)
            results[chapter] = result
            print(f"  风险等级: {result['risk_level']}")
            print(f"  AI概率: {result['overall_score']:.1%}\n")

    return results


def print_batch_summary(results: List[Dict]):
    """打印批量检测结果摘要"""
    print("\n" + "="*70)
    print("批量检测摘要".center(70))
    print("="*70)

    total = len(results)
    high_risk = sum(1 for r in results if r['result']['risk_level'] == '高风险')
    mid_risk = sum(1 for r in results if r['result']['risk_level'] == '中风险')
    low_risk = sum(1 for r in results if r['result']['risk_level'] == '低风险')
    safe = sum(1 for r in results if r['result']['risk_level'] == '安全')

    print(f"\n总文件数: {total}")
    print(f"高风险: {high_risk} ({high_risk/total*100:.1f}%)" if total > 0 else "")
    print(f"中风险: {mid_risk} ({mid_risk/total*100:.1f}%)" if total > 0 else "")
    print(f"低风险: {low_risk} ({low_risk/total*100:.1f}%)" if total > 0 else "")
    print(f"安全: {safe} ({safe/total*100:.1f}%)" if total > 0 else "")

    print("\n详细结果:")
    print("-"*70)

    for r in sorted(results, key=lambda x: x['result']['overall_score'], reverse=True):
        print(f"\n{r['file']}")
        print(f"  风险: {r['result']['risk_level']} | AI概率: {r['result']['overall_score']:.1%}")

        # 主要问题
        issues = []
        for test_name, test_result in r['result']['tests'].items():
            if test_result['score'] > 0.6:
                issues.append(test_name)
        if issues:
            print(f"  主要问题: {', '.join(issues)}")

    print("="*70 + "\n")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='批量AI检测工具')
    parser.add_argument('input', nargs='+', help='输入文件或目录')
    parser.add_argument('-o', '--output', help='输出JSON文件')
    parser.add_argument('--chapters', action='store_true', help='按章节检测模式')
    parser.add_argument('--chapter-names', nargs='+', help='自定义章节名称')

    args = parser.parse_args()

    if args.chapters:
        # 章节检测模式
        if len(args.input) != 1:
            print("错误: 章节检测模式需要单个输入文件")
            return

        with open(args.input[0], 'r', encoding='utf-8') as f:
            text = f.read()

        results = detect_chapters(text, args.chapter_names)

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"\n结果已保存到: {args.output}")
    else:
        # 文件批量检测模式
        file_paths = []

        for input_path in args.input:
            path = Path(input_path)
            if path.is_file():
                file_paths.append(str(path))
            elif path.is_dir():
                # 递归查找所有txt文件
                file_paths.extend(str(p) for p in path.rglob('*.txt'))
                file_paths.extend(str(p) for p in path.rglob('*.md'))

        if not file_paths:
            print("错误: 未找到任何文件")
            return

        results = batch_detect_files(file_paths, args.output)
        print_batch_summary(results)


if __name__ == '__main__':
    main()
