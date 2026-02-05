#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI检测工具API使用示例

演示如何在代码中直接调用ai_detector_all.py中的检测函数
"""

from ai_detector_all import (
    detect_vocabulary,
    detect_burstiness,
    detect_paraphrasing,
    detect_abstract,
    detect_comprehensive
)


# 示例文本
SAMPLE_TEXT = """
本文采用问卷调查方式对大学生网络使用行为进行了调查。
研究具有重要的理论意义和实践意义。
此外,研究还发现,上网时间越长的同学,成绩往往越低。
这个发现对学校的教育工作有参考价值。
首先,我们收集了数据。
其次,我们进行了分析。
最后,我们得出了结论。
"""

SAMPLE_ABSTRACT = """
本研究采用问卷调查法,对某高校500名大学生的网络使用行为进行了调查。
研究发现,大学生日均上网时间与学业成绩呈显著负相关。
具有重要的理论意义和实践意义,为高校教育管理提供参考。
"""


def example_vocabulary():
    """示例1: AI词汇密度检测"""
    print("=" * 60)
    print("示例1: AI词汇密度检测")
    print("=" * 60)

    result = detect_vocabulary(SAMPLE_TEXT)

    print(f"总字符数: {result['total_chars']}")
    print(f"AI词汇数: {result['ai_count']}")
    print(f"密度: {result['density_per_1000']} 个/1000字")
    print(f"风险等级: {result['risk_color']} {result['risk_level']}")

    # 使用建议
    if result['risk_level'] == '高风险':
        print("\n建议: 用具体数据代替空话,替换AI高频词汇")
    print()


def example_burstiness():
    """示例2: 句式突发性检测"""
    print("=" * 60)
    print("示例2: 句式突发性检测")
    print("=" * 60)

    result = detect_burstiness(SAMPLE_TEXT)

    print(f"句子数: {result['sentence_count']}")
    print(f"平均长度: {result['mean_length']} 字")
    print(f"变异系数: {result['cv']}")
    print(f"风险等级: {result['risk_color']} {result['risk_level']}")
    print(f"判断: {result['reason']}")
    print()


def example_paraphrasing():
    """示例3: 改写攻击检测"""
    print("=" * 60)
    print("示例3: 改写攻击检测")
    print("=" * 60)

    result = detect_paraphrasing(SAMPLE_TEXT)

    print(f"改写概率: {result['risk_score']:.1%}")
    print(f"风险等级: {result['risk_color']} {result['risk_level']}")

    if result['issues']:
        print("\n检测到的问题:")
        for issue in result['issues']:
            print(f"  - {issue}")
    print()


def example_abstract():
    """示例4: 摘要检测"""
    print("=" * 60)
    print("示例4: 摘要专用检测")
    print("=" * 60)

    result = detect_abstract(SAMPLE_ABSTRACT)

    print(f"摘要字数: {result['word_count']}")
    print(f"AI概率: {result['ai_probability']}%")
    print(f"风险等级: {result['risk_color']} {result['risk_level']}")

    if result['issues']:
        print("\n检测到的问题:")
        for issue in result['issues']:
            print(f"  - {issue}")

    # 根据风险等级给出建议
    if result['risk_level'] == '高风险':
        print("\n修改建议:")
        print("  1. 避免'本文''本研究'开头")
        print("  2. 删除'具有重要意义'等套话")
        print("  3. 加入具体数据")
    print()


def example_comprehensive():
    """示例5: 综合检测"""
    print("=" * 60)
    print("示例5: 综合检测")
    print("=" * 60)

    result = detect_comprehensive(SAMPLE_TEXT)

    print(f"综合得分: {result['overall_score']:.1%}")
    print(f"风险等级: {result['risk_level']}")

    print("\n各项测试:")
    for test_name, test_result in result['tests'].items():
        print(f"  {test_name}: {test_result['level']} ({test_result['score']:.2f})")

    print()

    # 根据综合评分给出建议
    score = result['overall_score']
    if score >= 0.7:
        print("严重警告: 文本表现出强烈的AI生成特征")
        print("建议大幅重写,加入个人观点和具体数据")
    elif score >= 0.5:
        print("警告: 文本可能包含AI生成内容")
        print("建议调整句式,减少AI词汇")
    elif score >= 0.3:
        print("注意: 文本存在轻微AI特征")
        print("建议微调优化")
    else:
        print("良好: 文本未表现出明显AI特征")
    print()


def example_conditional_check():
    """示例6: 条件判断"""
    print("=" * 60)
    print("示例6: 条件判断 - 自动决策")
    print("=" * 60)

    result = detect_comprehensive(SAMPLE_TEXT)

    # 根据检测结果自动决策
    if result['overall_score'] >= 0.7:
        action = "拒绝接受"
        reason = "AI率过高"
    elif result['overall_score'] >= 0.5:
        action = "要求修改"
        reason = "存在AI特征"
    elif result['overall_score'] >= 0.3:
        action = "建议优化"
        reason = "轻微AI特征"
    else:
        action = "接受"
        reason = "AI特征不明显"

    print(f"检测评分: {result['overall_score']:.1%}")
    print(f"处理决策: {action}")
    print(f"决策原因: {reason}")
    print()


def example_batch_check():
    """示例7: 批量检测多个文本"""
    print("=" * 60)
    print("示例7: 批量检测")
    print("=" * 60)

    texts = {
        "摘要": SAMPLE_ABSTRACT,
        "正文": SAMPLE_TEXT,
        "自然文本": "我觉得这个研究很有意思。数据显示,每天上网超过3小时的同学,成绩平均下降了15分。这个发现让我很担心。"
    }

    results = {}
    for name, text in texts.items():
        result = detect_comprehensive(text)
        results[name] = result
        print(f"{name}: {result['risk_level']} ({result['overall_score']:.1%})")

    # 找出需要修改的部分
    print("\n需要关注的部分:")
    for name, result in results.items():
        if result['overall_score'] > 0.5:
            print(f"  ⚠️  {name}: AI率 {result['overall_score']:.1%}")
    print()


def main():
    """运行所有示例"""
    print("\n" + "=" * 60)
    print("AI检测工具API使用示例".center(60))
    print("=" * 60 + "\n")

    example_vocabulary()
    example_burstiness()
    example_paraphrasing()
    example_abstract()
    example_comprehensive()
    example_conditional_check()
    example_batch_check()

    print("=" * 60)
    print("所有示例运行完成!")
    print("=" * 60)


if __name__ == '__main__':
    main()
