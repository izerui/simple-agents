#!/usr/bin/env python3
"""
综合AI检测脚本
Comprehensive AI Detection for Chinese Academic Writing

整合多种检测方法：
1. AI词汇密度分析
2. 句式突发性检查
3. 改写攻击检测
4. 统计特征分析
5. 模式识别

基于论文"Can AI-Generated Text be Reliably Detected?"的研究成果
"""

import re
import jieba
import numpy as np
from typing import Dict, List
from collections import Counter


class ComprehensiveAIDetector:
    """综合AI检测器"""

    def __init__(self):
        # AI高频词汇库
        self.ai_vocab = {
            'connection': [
                '此外', '同时', '另外', '再者', '总体而言', '综上所述',
                '而且', '并且', '进而', '从而', '首先', '其次', '最后',
                '一方面', '另一方面', '另外', '再次'
            ],
            'adjective': [
                '重要的', '关键的', '核心的', '显著的', '深刻的', '基本的',
                '主要的', '本质的', '根本的', '重大的', '关键的', '核心的'
            ],
            'verb': [
                '体现', '反映', '展现', '表明', '涵盖', '包含', '包括',
                '促进', '推动', '助力', '提升', '改善', '增强'
            ],
            'formula': [
                '具有重要', '提供参考', '具有重要意义', '具有重要意义',
                '具有重要的', '具有一定的', '起到了一定的'
            ]
        }

        # 公式化开头模式
        self.formula_starts = [
            r'^本文.*?(采用|使用|利用|通过)',
            r'^本研究.*?(采用|使用|利用|通过)',
            r'^本研究.*?(旨在|在于|关注)',
            r'^文章.*?(分析|探讨|研究)',
        ]

    def detect(self, text: str, detailed: bool = True) -> Dict:
        """
        综合检测

        Args:
            text: 待检测文本
            detailed: 是否返回详细分析

        Returns:
            检测结果
        """
        results = {
            'overall_score': 0.0,
            'risk_level': 'unknown',
            'tests': {}
        }

        # 测试1: AI词汇密度
        vocab_result = self._test_vocabulary_density(text)
        results['tests']['vocabulary_density'] = vocab_result

        # 测试2: 句式突发性
        burstiness_result = self._test_burstiness(text)
        results['tests']['burstiness'] = burstiness_result

        # 测试3: 公式化结构
        formula_result = self._test_formulaic_structure(text)
        results['tests']['formulaic_structure'] = formula_result

        # 测试4: 统计特征
        stats_result = self._test_statistical_features(text)
        results['tests']['statistical_features'] = stats_result

        # 测试5: 模式识别
        pattern_result = self._test_patterns(text)
        results['tests']['patterns'] = pattern_result

        # 计算总分
        weights = {
            'vocabulary_density': 0.3,
            'burstiness': 0.25,
            'formulaic_structure': 0.2,
            'statistical_features': 0.15,
            'patterns': 0.1
        }

        results['overall_score'] = sum(
            results['tests'][test]['score'] * weights[test]
            for test in weights.keys()
        )

        # 风险等级
        if results['overall_score'] >= 0.7:
            results['risk_level'] = '高风险'
        elif results['overall_score'] >= 0.5:
            results['risk_level'] = '中风险'
        elif results['overall_score'] >= 0.3:
            results['risk_level'] = '低风险'
        else:
            results['risk_level'] = '安全'

        return results

    def _test_vocabulary_density(self, text: str) -> Dict:
        """测试1: AI词汇密度"""
        # 分词
        words = list(jieba.cut(text))
        total_chars = len(text)

        # 统计AI词汇
        all_ai_words = []
        for category in self.ai_vocab.values():
            all_ai_words.extend(category)

        ai_word_count = sum(text.count(word) for word in all_ai_words)
        density = (ai_word_count / total_chars) * 1000 if total_chars > 0 else 0

        # 评分
        if density > 50:
            score = 1.0
            level = '高风险'
        elif density > 30:
            score = 0.6
            level = '中风险'
        else:
            score = 0.2
            level = '安全'

        return {
            'score': score,
            'level': level,
            'density': density,
            'ai_words_per_1000': ai_word_count,
            'total_chars': total_chars
        }

    def _test_burstiness(self, text: str) -> Dict:
        """测试2: 句式突发性"""
        # 分句
        sentences = re.split(r'[。！？；]', text)
        sentences = [s.strip() for s in sentences if 5 < len(s.strip()) < 200]

        if len(sentences) < 5:
            return {'score': 0.0, 'level': '数据不足', 'reason': '句子数量太少'}

        # 计算句子长度
        lengths = np.array([len(s) for s in sentences])
        std_dev = np.std(lengths)
        mean_len = np.mean(lengths)
        cv = std_dev / mean_len if mean_len > 0 else 0  # 变异系数

        # 评分（标准差越大，突发性越高，AI特征越少）
        if cv < 0.15:
            score = 1.0
            level = '高风险'
            reason = '句子长度过于一致'
        elif cv < 0.25:
            score = 0.5
            level = '中风险'
            reason = '变化程度较低'
        else:
            score = 0.1
            level = '安全'
            reason = '变化自然'

        return {
            'score': score,
            'level': level,
            'cv': cv,
            'mean_length': mean_len,
            'std_dev': std_dev,
            'min_length': np.min(lengths),
            'max_length': np.max(lengths),
            'reason': reason
        }

    def _test_formulaic_structure(self, text: str) -> Dict:
        """测试3: 公式化结构"""
        paragraphs = text.split('\n')
        paragraphs = [p.strip() for p in paragraphs if len(p.strip()) > 20]

        formula_count = 0
        total_sentences = 0

        for para in paragraphs:
            sentences = re.split(r'[。！？]', para)
            sentences = [s.strip() for s in sentences if len(s.strip()) > 5]

            for sent in sentences:
                total_sentences += 1
                # 检查公式化开头
                for pattern in self.formula_starts:
                    if re.match(pattern, sent):
                        formula_count += 1
                        break

        # 检查模糊引用
        vague_refs = len(re.findall(r'(研究表明|学者认为|学者指出|研究显示)(?=，|。)', text))

        # 评分
        formula_ratio = formula_count / total_sentences if total_sentences > 0 else 0

        if formula_ratio > 0.3 or vague_refs > 3:
            score = 1.0
            level = '高风险'
        elif formula_ratio > 0.15 or vague_refs > 1:
            score = 0.5
            level = '中风险'
        else:
            score = 0.1
            level = '安全'

        return {
            'score': score,
            'level': level,
            'formula_ratio': formula_ratio,
            'vague_refs': vague_refs,
            'formula_count': formula_count,
            'total_sentences': total_sentences
        }

    def _test_statistical_features(self, text: str) -> Dict:
        """测试4: 统计特征"""
        # 分词
        words = list(jieba.cut(text))
        words = [w for w in words if len(w) > 1]

        if len(words) < 50:
            return {'score': 0.0, 'level': '数据不足'}

        # 词汇多样性
        unique_ratio = len(set(words)) / len(words)

        # 标点符号使用
        punct_count = Counter(re.findall(r'[，。；：！？、]', text))
        total_punct = sum(punct_count.values())
        comma_ratio = punct_count['，'] / total_punct if total_punct > 0 else 0

        # n-gram分析（简化版）
        bigrams = []
        for i in range(len(words) - 1):
            bigrams.append(words[i] + words[i+1])
        bigram_diversity = len(set(bigrams)) / len(bigrams) if bigrams else 0

        # 评分
        suspicious_count = 0
        reasons = []

        if unique_ratio > 0.75:
            suspicious_count += 1
            reasons.append('词汇多样性异常高')
        if comma_ratio > 0.6:
            suspicious_count += 1
            reasons.append('逗号使用频率过高')
        if bigram_diversity > 0.8:
            suspicious_count += 1
            reasons.append('词组组合过于多样')

        score = suspicious_count / 3
        if score >= 0.67:
            level = '高风险'
        elif score >= 0.33:
            level = '中风险'
        else:
            level = '安全'
            reasons = ['统计特征正常']

        return {
            'score': score,
            'level': level,
            'unique_ratio': unique_ratio,
            'comma_ratio': comma_ratio,
            'bigram_diversity': bigram_diversity,
            'reasons': reasons
        }

    def _test_patterns(self, text: str) -> Dict:
        """测试5: 模式识别"""
        issues = []

        # 检查虚词堆砌
        stuffy_pattern = r'((重要的|关键的|核心的|显著的)\s+){2,}'
        if re.search(stuffy_pattern, text):
            issues.append('虚词堆砌')

        # 检查"具有重要意义"类套话
        cliches = [
            '具有重要的理论意义',
            '具有重要的实践意义',
            '具有重要的参考价值',
            '提供了重要参考'
        ]
        found_cliches = [c for c in cliches if c in text]
        if found_cliches:
            issues.append(f'套话: {", ".join(found_cliches[:2])}')

        # 检查AI公式化表达
        ai_phrases = [
            '采用常规方法',
            '按照标准流程',
            '进行深入研究',
            '展开全面分析'
        ]
        found_ai = [p for p in ai_phrases if p in text]
        if found_ai:
            issues.append(f'AI表达: {", ".join(found_ai[:2])}')

        # 检查是否有具体数据
        has_data = bool(re.search(r'\d+%|\d+分|\d+个|\d+人', text))

        # 检查是否有第一人称
        has_first_person = bool(re.search(r'(我|笔者|我们)(认为|发现|觉得)', text))

        # 评分
        score = min(len(issues) / 5, 1.0)
        if not has_data and not has_first_person:
            score += 0.2

        if score >= 0.7:
            level = '高风险'
        elif score >= 0.4:
            level = '中风险'
        else:
            level = '安全'

        return {
            'score': min(score, 1.0),
            'level': level,
            'issues': issues,
            'has_data': has_data,
            'has_first_person': has_first_person
        }


def print_comprehensive_report(results: Dict):
    """打印综合报告"""
    print("\n" + "="*70)
    print("AI文本综合检测报告".center(70))
    print("="*70)

    print(f"\n【综合评分】")
    print(f"  风险等级: {results['risk_level']}")
    print(f"  AI概率: {results['overall_score']:.1%}")

    print(f"\n【各项测试结果】")
    print("-"*70)

    test_names = {
        'vocabulary_density': 'AI词汇密度',
        'burstiness': '句式突发性',
        'formulaic_structure': '公式化结构',
        'statistical_features': '统计特征',
        'patterns': '模式识别'
    }

    for key, name in test_names.items():
        test = results['tests'][key]
        print(f"\n{name}:")
        print(f"  风险等级: {test['level']}")
        print(f"  得分: {test['score']:.2f}/1.00")

        # 详细信息
        if key == 'vocabulary_density':
            print(f"  AI词汇密度: {test['density']:.1f}个/1000字")
        elif key == 'burstiness':
            print(f"  句子长度: 平均{test['mean_length']:.1f}字 ± {test['std_dev']:.2f}")
            print(f"  变异系数: {test['cv']:.2f}")
            print(f"  判断: {test['reason']}")
        elif key == 'formulaic_structure':
            print(f"  公式化比例: {test['formula_ratio']:.1%}")
            print(f"  模糊引用: {test['vague_refs']}处")
        elif key == 'statistical_features':
            print(f"  词汇多样性: {test['unique_ratio']:.2%}")
            print(f"  分析: {', '.join(test['reasons'])}")
        elif key == 'patterns':
            if test['issues']:
                print(f"  发现问题:")
                for issue in test['issues'][:5]:
                    print(f"    - {issue}")
            else:
                print(f"  未发现明显问题")
            print(f"  包含数据: {'是' if test['has_data'] else '否'}")
            print(f"  第一人称: {'是' if test['has_first_person'] else '否'}")

    print("\n" + "="*70)

    # 总体建议
    score = results['overall_score']
    if score >= 0.7:
        print("\n【严重警告】文本表现出强烈的AI生成特征")
        print("\n建议修改:")
        print("1. 大幅重写，使用自己的语言")
        print("2. 加入具体数据和实例")
        print("3. 使用第一人称表达个人观点")
        print("4. 打破公式化结构，增加变化")
        print("5. 删除所有'重要''关键'等虚词")
    elif score >= 0.5:
        print("\n【警告】文本可能包含AI生成内容")
        print("\n建议修改:")
        print("1. 调整句子长度，增加变化")
        print("2. 减少AI词汇使用")
        print("3. 加入个人观点和数据")
        print("4. 避免公式化开头")
    elif score >= 0.3:
        print("\n【注意】文本存在轻微AI特征")
        print("\n建议优化:")
        print("1. 微调句子节奏")
        print("2. 增加个人表达")
        print("3. 添加具体数据")
    else:
        print("\n【良好】文本未表现出明显AI特征")
        print("继续保持自然、有个性的写作风格！")

    print("="*70 + "\n")


def main():
    """主函数"""
    import sys

    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            text = f.read()
    else:
        # 示例文本
        text = """
        本文采用实证研究方法，对大学生网络使用行为进行了深入分析。
        研究表明，网络使用时间与学习成绩呈负相关。
        学者们普遍认为，网络使用对大学生学习有重要影响。
        此外，网络使用还会影响大学生的社交能力。
        同时，网络使用也对大学生的身体健康产生重要影响。
        本研究对于高校教育管理具有重要的理论和实践意义。
        """

    detector = ComprehensiveAIDetector()
    results = detector.detect(text)
    print_comprehensive_report(results)


if __name__ == '__main__':
    main()
