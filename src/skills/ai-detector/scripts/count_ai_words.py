#!/usr/bin/env python3
"""
AI词汇统计工具

快速统计论文中的AI高频词汇密度，用于初步AI率风险评估。
使用方法：python scripts/count_ai_words.py 论文.txt
"""

import argparse
import re
import sys
from pathlib import Path
from collections import Counter


# AI高频词汇列表
AI_WORDS = {
    # 连接词/过渡词
    "此外", "同时", "另外", "再者", "总体而言", "综上所述", "总的来说",
    # 形容词/副词
    "重要的", "关键的", "核心的", "显著的", "深刻的", "全面的", "系统的",
    "促进", "推动", "助力", "支撑", "增强", "提升",
    # 动词
    "体现", "反映", "展现", "表明", "涵盖", "包含", "涉及", "覆盖",
    "强调", "突出", "彰显", "凸显",
    # 虚词
    "具有重要", "具有重要理论", "具有重要实践", "具有重要的",
    "提供参考", "具有重要的参考价值", "重要参考",
    # 其他
    "深入分析", "详细分析", "全面分析", "综合分析",
    "关键因素", "核心因素", "主要因素",
    "理论意义", "实践意义",
    "值得关注", "值得注意", "需要指出"
}


def count_ai_words(text):
    """统计AI高频词汇出现次数"""
    count = 0
    found_words = []

    text_lower = text.lower()
    words_to_check = {word.lower(): word for word in AI_WORDS}

    for word, original in words_to_check.items():
        # 使用词边界匹配
        pattern = r'\b' + re.escape(word) + r'\b'
        matches = re.findall(pattern, text_lower)
        if matches:
            count += len(matches)
            found_words.extend([original] * len(matches))

    return count, found_words


def calculate_burstiness(text):
    """计算句式突发性（句子长度变化程度）"""
    # 按句号、问号、感叹号、分号分割
    sentences = re.split(r'[。！？；；]', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if len(sentences) < 2:
        return 0, 0  # 无法计算

    # 统计每句字数
    lengths = [len(s) for s in sentences]

    # 计算标准差（突发性指标）
    mean_length = sum(lengths) / len(lengths)
    variance = sum((l - mean_length) ** 2 for l in lengths) / len(lengths)
    std_dev = variance ** 0.5

    # 计算最大最小差异
    max_len = max(lengths)
    min_len = min(lengths)
    diff = max_len - min_len

    return std_dev, diff


def detect_formulaic_patterns(text):
    """检测公式化结构模式"""
    issues = []

    # 检查"本文""本研究"开头
    if text.startswith("本文") or text.startswith("本研究"):
        issues.append("公式化开头：'本文'/'本研究'")

    # 检查"综上所述""总之"等总结词
    conclusion_patterns = [
        r'综上所述.{0,10}',
        r'总之.{0,10}',
        r'总的来说.{0,10}'
    ]
    for pattern in conclusion_patterns:
        if re.search(pattern, text):
            issues.append(f"公式化总结词：'{re.search(pattern, text).group()[:10]}...'")
            break

    # 检查"具有重要意义""提供参考"等套话
    cliches = [
        "具有重要的理论意义",
        "具有重要的实践意义",
        "具有重要的理论和实践意义",
        "提供参考",
        "提供借鉴"
    ]
    for cliche in cliches:
        if cliche in text:
            issues.append(f"套话：'{cliche}'")

    return issues


def analyze_file(filepath):
    """分析文件"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
    except Exception as e:
        print(f"Error reading file: {e}")
        return None

    word_count = len(text.split())

    # 统计AI词汇
    ai_count, ai_words = count_ai_words(text)
    ai_density = (ai_count / word_count * 1000) if word_count > 0 else 0

    # 计算突发性
    std_dev, diff = calculate_burstiness(text)

    # 检测公式化模式
    issues = detect_formulaic_patterns(text)

    # 评估风险等级
    if ai_density > 50:
        risk = "高风险"
    elif ai_density > 30:
        risk = "中等风险"
    else:
        risk = "正常"

    return {
        'word_count': word_count,
        'ai_count': ai_count,
        'ai_density': round(ai_density, 1),
        'burstiness_std': round(std_dev, 1),
        'burstiness_diff': diff,
        'risk_level': risk,
        'found_words': ai_words[:10] if ai_words else [],  # 只显示前10个
        'issues': issues
    }


def print_report(result):
    """打印分析报告"""
    print("\n" + "="*60)
    print("AI词汇检测报告")
    print("="*60)

    if result is None:
        return

    print(f"\n总字数: {result['word_count']}")
    print(f"AI词汇数量: {result['ai_count']}")
    print(f"AI词汇密度: {result['ai_density']} 个/1000字")
    print(f"句式突发性:")
    print(f"  标准差: {result['burstiness_std']}")
    print(f"  最大最小差: {result['burstiness_diff']}")
    print(f"\n风险等级: {result['risk_level']}")

    if result['found_words']:
        print(f"\n检测到的AI词汇（前10个）:")
        for word in result['found_words']:
            print(f"  - {word}")

    if result['issues']:
        print(f"\n公式化模式问题:")
        for issue in result['issues']:
            print(f"  ⚠️  {issue}")

    # 建议
    print(f"\n建议:")
    if result['risk_level'] == "高风险":
        print("  需要大幅修改。建议：")
        print("  1. 用具体数据代替空话")
        print("  2. 打破公式化结构")
        print("  3. 加入个人观点和分析")
    elif result['risk_level'] == "中等风险":
        print("  建议局部修改。重点关注：")
        print("  1. 替换AI高频词汇")
        print("  2. 增加句式变化")
        print("  3. 加入具体细节")
    else:
        print("  AI率正常，继续保持！")

    # 突发性分析
    if result['burstiness_diff'] < 5:
        print(f"\n⚠️  句式变化较小（差异仅{result['burstiness_diff']}字）")
        print("  建议：故意改变句子长度，加入一些短句或长句")
    elif result['burstiness_diff'] > 10:
        print(f"✓  句式变化自然（差异{result['burstiness_diff']}字）")
    else:
        print(f"  句式变化中等（差异{result['burstiness_diff']}字）")

    print("\n" + "="*60)


def main():
    parser = argparse.ArgumentParser(
        description="统计论文中的AI高频词汇密度"
    )
    parser.add_argument('file', help='要分析的论文文件')
    parser.add_argument('--detail', '-d', action='store_true',
                       help='显示检测到的AI词汇列表')

    args = parser.parse_args()

    result = analyze_file(args.file)

    if result:
        print_report(result)

        if args.detail and result['found_words']:
            print(f"\n完整AI词汇列表（{len(result['found_words'])}次）:")
            word_counts = Counter(result['found_words'])
            for word, count in word_counts.most_common():
                print(f"  {word}: {count}次")


if __name__ == "__main__":
    main()
