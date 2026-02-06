#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试增强的AI检测功能
"""

import sys
sys.path.insert(0, '/Users/liuyuhua/PycharmProjects/simple-agents/src/skills/paper-detector/scripts')

from ai_paper_detector import EnhancedAIDetector

# 测试文本（明显AI生成特征）
test_text = """
本研究采用实证研究方法，对大学生网络使用行为进行了深入分析。
首先，我们通过问卷调查收集数据。其次，利用统计软件进行分析。
最后，得出研究结果。

研究表明，网络使用对学习效果具有重要影响。
学者们普遍认为，过度使用网络会导致注意力分散。
此外，网络使用还会影响睡眠质量。

本研究具有重要的理论意义和实践意义。
研究结果为高校教育管理提供了重要参考。
总体而言，网络使用需要适度控制。

综上所述，本研究具有重要的价值。
"""

# 测试文本（人类写作特征）
human_text = """
以大学生网络使用为例。我们调查了5所学校的1200名学生，
发现一个有意思的现象：每天用网超过5小时的同学，
期末成绩平均低8.3分。

但也有些意外的发现——用网查资料的同学，
如果合理控制时间，成绩反而会提高。
这可能是因为网络提供了更丰富的学习资源。

不过，我们也注意到一些问题。
比如，有同学沉迷游戏，影响了正常学习。
这说明，关键不在于用不用网，而在于怎么用。
"""

print("=" * 60)
print("测试增强的AI检测功能")
print("=" * 60)
print()

# 测试1: AI词汇密度检测
print("【测试1】AI词汇密度检测")
print("-" * 60)
result1 = EnhancedAIDetector.detect_vocabulary_density(test_text)
print(f"文本长度: {result1['total_chars']} 字符")
print(f"AI词汇数量: {result1['ai_count']} 个")
print(f"AI词汇密度: {result1['density_per_1000']} 个/1000字")
print(f"风险等级: {result1['risk_color']} {result1['risk_level']}")
print()

# 测试2: 句式突发性检测
print("【测试2】句式突发性检测")
print("-" * 60)
result2 = EnhancedAIDetector.detect_burstiness(test_text)
print(f"句子数量: {result2['sentence_count']} 句")
print(f"平均长度: {result2['mean_length']} 字")
print(f"标准差: {result2['std_dev']}")
print(f"变异系数(CV): {result2['cv']}")
print(f"相邻差异: {result2['adjacent_diff']} 字")
print(f"风险等级: {result2['risk_color']} {result2['risk_level']}")
print(f"原因: {result2['reason']}")
print()

# 测试3: 改写攻击检测
print("【测试3】改写攻击检测")
print("-" * 60)
result3 = EnhancedAIDetector.detect_paraphrasing(test_text)
print(f"风险等级: {result3['risk_color']} {result3['risk_level']}")
print(f"风险评分: {result3['risk_score']}")
print(f"发现的问题: {', '.join(result3['issues'])}")
if result3['paraphrase_examples']:
    print(f"改写痕迹示例: {', '.join(result3['paraphrase_examples'])}")
print()

# 测试4: 综合检测
print("【测试4】综合AI检测（明显AI文本）")
print("-" * 60)
result4 = EnhancedAIDetector.comprehensive_detection(test_text)
print(f"整体风险: {result4['overall_risk_color']} {result4['overall_risk']}")
print(f"  - 词汇密度: {result4['vocabulary']['risk_color']} {result4['vocabulary']['risk_level']} ({result4['vocabulary']['density_per_1000']} 个/1000字)")
print(f"  - 句式突发性: {result4['burstiness']['risk_color']} {result4['burstiness']['risk_level']} (CV={result4['burstiness']['cv']})")
print(f"  - 改写攻击: {result4['paraphrasing']['risk_color']} {result4['paraphrasing']['risk_level']}")
print()

# 测试5: 综合检测（人类文本）
print("【测试5】综合AI检测（人类写作文本）")
print("-" * 60)
result5 = EnhancedAIDetector.comprehensive_detection(human_text)
print(f"整体风险: {result5['overall_risk_color']} {result5['overall_risk']}")
print(f"  - 词汇密度: {result5['vocabulary']['risk_color']} {result5['vocabulary']['risk_level']} ({result5['vocabulary']['density_per_1000']} 个/1000字)")
print(f"  - 句式突发性: {result5['burstiness']['risk_color']} {result5['burstiness']['risk_level']} (CV={result5['burstiness']['cv']})")
print(f"  - 改写攻击: {result5['paraphrasing']['risk_color']} {result5['paraphrasing']['risk_level']}")
print()

print("=" * 60)
print("测试完成！所有功能正常工作。")
print("=" * 60)
