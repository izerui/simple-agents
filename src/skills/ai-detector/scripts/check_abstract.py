#!/usr/bin/env python3
"""
摘要AI率快速检测

专门针对论文摘要进行AI率快速评估。
摘要是最容易AI高的部分，需要特别关注。
使用方法：python scripts/check_abstract.py "摘要内容"
"""

import argparse
import re
import sys


def check_abstract(text):
    """检查摘要的AI特征"""

    issues = []
    score = 0
    max_score = 100

    # 检查1: 公式化开头 (-20分)
    if text.startswith("本文") or text.startswith("本研究"):
        issues.append("❌ 公式化开头：'本文'/'本研究'开头")
        score += 20

    # 检查2: AI高频词汇密度 (-40分)
    ai_words = [
        "此外", "同时", "另外", "再者", "综上所述", "总的来说",
        "重要的", "关键的", "核心的", "显著的", "深刻的",
        "体现", "反映", "展现", "表明", "涵盖", "包含",
        "具有重要意义", "具有理论", "具有实践", "提供参考"
    ]

    text_lower = text.lower()
    ai_count = 0
    for word in ai_words:
        ai_count += text_lower.count(word)

    density = ai_count / len(text) * 100 if text else 0

    if density > 5:  # 每100字超过5个
        issues.append(f"❌ AI词汇密度高: {density:.1f}% (每100字{ai_count*10:.0f}个)")
        score += 40
    elif density > 3:
        issues.append(f"⚠️  AI词汇密度中等: {density:.1f}%")
        score += 20
    else:
        issues.append("✓ AI词汇密度正常")

    # 检查3: 套话虚词 (-20分)
    cliches = [
        "具有重要的理论意义", "具有重要的实践意义",
        "具有重要的理论和实践意义",
        "提供参考", "提供借鉴", "具有重要的参考价值",
        "具有重要意义", "具有重要"
    ]

    for cliche in cliches:
        if cliche in text:
            issues.append(f"❌ 套话虚词: '{cliche}'")
            score += 20
            break

    # 检查4: 句式变化 (-20分)
    sentences = re.split(r'[。；;]', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if len(sentences) >= 3:
        lengths = [len(s) for s in sentences[:5]]  # 取前5句
        diff = max(lengths) - min(lengths)
        if diff < 5:
            issues.append(f"❌ 句式变化小: 前5句长度差异仅{diff}字")
            score += 20
        else:
            issues.append(f"✓ 句式变化自然")

    # 检查5: 具体数据/细节 (+20分改善)
    has_numbers = bool(re.search(r'\d+', text))
    has_quotes = bool(re.search('"[^"]{1,20}"', text))

    if has_numbers and has_quotes:
        issues.append("✓ 有具体数据和引用")
        score -= 20
    elif has_numbers:
        issues.append("⚠️  有数据但缺少引用")
        score -= 10
    else:
        issues.append("❌ 缺乏具体数据")

    # 计算AI率
    ai_probability = min(score, 100)

    return {
        'score': score,
        'ai_probability': ai_probability,
        'issues': issues,
        'word_count': len(text),
        'ai_count': ai_count,
        'density': density
    }


def print_report(result):
    """打印报告"""
    print("\n" + "="*50)
    print("摘要AI率检测报告")
    print("="*50)

    print(f"\n摘要字数: {result['word_count']}")
    print(f"AI词汇数量: {result['ai_count']}")
    print(f"AI词汇密度: {result['density']:.1f}% (每100字)")
    print(f"\nAI概率评估: {result['ai_probability']}%")

    if result['ai_probability'] >= 60:
        risk = "🔴 高风险 - 需要大幅修改"
    elif result['ai_probability'] >= 40:
        risk = "🟡 中等风险 - 建议修改"
    elif result['ai_probability'] >= 20:
        risk = "🟢 低风险 - 可接受"
    else:
        risk = "🟢 很低风险 - 良好"

    print(f"\n风险等级: {risk}")

    print("\n检测结果:")
    for issue in result['issues']:
        print(f"  {issue}")

    print("\n修改建议:")
    if result['ai_probability'] >= 60:
        print("  1. 不要'本文''本研究'开头，直接说研究发现")
        print("  2. 用具体数据代替空话")
        print("  3. 避免'重要意义''提供参考'等套话")
        print("  4. 加入转折和意外发现")
    elif result['ai_probability'] >= 40:
        print("  1. 替换部分AI词汇")
        print("  2. 增加句式变化")
        print("  3. 加入具体细节")
    else:
        print("  摘要质量良好！")


def main():
    parser = argparse.ArgumentParser(
        description="快速检测摘要的AI率"
    )
    parser.add_argument('text', help='摘要内容（用引号括起来）')
    parser.add_argument('--file', '-f', help='从文件读取摘要')

    args = parser.parse_args()

    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                text = f.read()
        except Exception as e:
            print(f"Error reading file: {e}")
            return
    else:
        text = args.text

    result = check_abstract(text)
    print_report(result)


if __name__ == "__main__":
    main()
