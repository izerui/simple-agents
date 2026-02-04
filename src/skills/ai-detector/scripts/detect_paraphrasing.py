#!/usr/bin/env python3
"""
改写攻击检测脚本
Detect Paraphrasing Attacks in Chinese Academic Writing

基于论文"Can AI-Generated Text be Reliably Detected?"的改写攻击检测方法
识别经过改写工具处理后的AI生成文本。

检测特征：
1. 词汇多样性异常
2. 句子结构一致性过高
3. 缺乏个人声音
4. 改写痕迹识别
"""

import re
import numpy as np
from typing import Dict, List, Tuple
import jieba
from collections import Counter


class ParaphrasingDetector:
    """改写攻击检测器"""

    def __init__(self):
        # 改写工具常用的句式模板
        self.paraphrasing_patterns = [
            r'我们.*?了.*?方式',
            r'采用.*?方法',
            r'通过.*?途径',
            r'使用.*?手段',
            r'以.*?为例',
        ]

        # AI高频连接词（改写后可能保留）
        self.connection_words = [
            '此外', '同时', '另外', '再者', '总体而言', '综上所述',
            '而且', '并且', '再者', '进而', '从而'
        ]

        # 改写工具常用的词汇替换模式
        self.replacement_pairs = {
            '采用': ['使用', '利用', '运用', '采取'],
            '方法': ['方式', '手段', '途径', '方法'],
            '表明': ['显示', '说明', '指出', '揭示'],
            '重要的': ['关键的', '核心的', '主要的', '基本的'],
        }

    def detect(self, text: str) -> Dict:
        """
        检测文本是否可能经过改写攻击

        Args:
            text: 待检测的文本

        Returns:
            检测结果字典，包含各种指标和判断
        """
        results = {
            'paraphrasing_probability': 0.0,
            'indicators': [],
            'details': {}
        }

        # 1. 词汇多样性分析
        vocab_diversity = self._check_vocabulary_diversity(text)
        results['details']['vocabulary_diversity'] = vocab_diversity
        if vocab_diversity['is_suspicious']:
            results['indicators'].append('词汇多样性异常')
            results['paraphrasing_probability'] += 0.25

        # 2. 句子结构一致性
        structure_consistency = self._check_structure_consistency(text)
        results['details']['structure_consistency'] = structure_consistency
        if structure_consistency['is_suspicious']:
            results['indicators'].append('句子结构过于一致')
            results['paraphrasing_probability'] += 0.25

        # 3. 改写痕迹检测
        paraphrasing_marks = self._detect_paraphrasing_patterns(text)
        results['details']['paraphrasing_marks'] = paraphrasing_marks
        if paraphrasing_marks['count'] > 3:
            results['indicators'].append(f'发现{paraphrasing_marks["count"]}处改写痕迹')
            results['paraphrasing_probability'] += 0.25

        # 4. 个人声音缺失
        personal_voice = self._check_personal_voice(text)
        results['details']['personal_voice'] = personal_voice
        if not personal_voice['has_personal_voice']:
            results['indicators'].append('缺乏个人表达特征')
            results['paraphrasing_probability'] += 0.25

        # 归一化概率
        results['paraphrasing_probability'] = min(results['paraphrasing_probability'], 1.0)

        # 风险等级
        if results['paraphrasing_probability'] >= 0.75:
            results['risk_level'] = '高风险'
        elif results['paraphrasing_probability'] >= 0.5:
            results['risk_level'] = '中风险'
        elif results['paraphrasing_probability'] >= 0.25:
            results['risk_level'] = '低风险'
        else:
            results['risk_level'] = '安全'

        return results

    def _check_vocabulary_diversity(self, text: str) -> Dict:
        """检查词汇多样性"""
        # 分词
        words = list(jieba.cut(text))
        words = [w for w in words if len(w) > 1 and w.strip()]

        if len(words) < 50:
            return {'is_suspicious': False, 'ratio': 0, 'reason': '文本太短'}

        # 计算词汇丰富度
        unique_words = len(set(words))
        total_words = len(words)
        diversity_ratio = unique_words / total_words

        # 改写后的文本通常词汇多样性异常高或异常低
        # 正常中文写作约为0.5-0.7
        is_suspicious = diversity_ratio > 0.8 or diversity_ratio < 0.4

        return {
            'is_suspicious': is_suspicious,
            'ratio': diversity_ratio,
            'unique_words': unique_words,
            'total_words': total_words,
            'reason': '词汇多样性异常' if is_suspicious else '正常范围'
        }

    def _check_structure_consistency(self, text: str) -> Dict:
        """检查句子结构一致性"""
        # 分句
        sentences = re.split(r'[。！？；]', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 5]

        if len(sentences) < 5:
            return {'is_suspicious': False, 'std_dev': 0, 'reason': '句子数量不足'}

        # 计算句子长度
        lengths = [len(s) for s in sentences]
        std_dev = np.std(lengths)
        mean_length = np.mean(lengths)

        # 改写后的文本句子长度标准差通常很小（过于一致）
        is_suspicious = std_dev < mean_length * 0.2

        return {
            'is_suspicious': is_suspicious,
            'std_dev': std_dev,
            'mean_length': mean_length,
            'min_length': min(lengths),
            'max_length': max(lengths),
            'reason': '句子长度过于一致' if is_suspicious else '正常变化'
        }

    def _detect_paraphrasing_patterns(self, text: str) -> Dict:
        """检测改写模式"""
        count = 0
        patterns_found = []

        for pattern in self.paraphrasing_patterns:
            matches = re.findall(pattern, text)
            if matches:
                count += len(matches)
                patterns_found.extend(matches[:3])  # 只记录前3个

        # 检测词汇替换对
        for original, replacements in self.replacement_pairs.items():
            if original in text:
                for replacement in replacements:
                    if replacement in text and replacement != original:
                        count += 1
                        patterns_found.append(f'{original} → {replacement}')

        return {
            'count': count,
            'patterns': patterns_found
        }

    def _check_personal_voice(self, text: str) -> Dict:
        """检查个人声音"""
        # 个人表达特征
        personal_indicators = [
            r'我认为', r'在我看来', r'笔者',
            r'我们发现', r'值得注意的是',
            r'本研究也有', r'这可能是因为',
            r'最初的', r'但.*?发现',
        ]

        has_personal = False
        found_patterns = []

        for pattern in personal_indicators:
            if re.search(pattern, text):
                has_personal = True
                found_patterns.append(pattern)

        # 检查是否有具体数据引用
        has_data = bool(re.search(r'\d+.*?%|\d+.*?分|\d+.*?个', text))

        # 检查是否有转折和意外
        has_contrast = bool(re.search(r'但|然而|不过|反|而', text))

        return {
            'has_personal_voice': has_personal or has_data or has_contrast,
            'personal_patterns': found_patterns,
            'has_data': has_data,
            'has_contrast': has_contrast
        }


def print_report(text: str, results: Dict):
    """打印检测报告"""
    print("\n" + "="*60)
    print("改写攻击检测报告".center(60))
    print("="*60)

    print(f"\n【风险等级】: {results['risk_level']}")
    print(f"【改写概率】: {results['paraphrasing_probability']:.1%}")

    if results['indicators']:
        print(f"\n【检测到的问题】:")
        for i, indicator in enumerate(results['indicators'], 1):
            print(f"  {i}. {indicator}")
    else:
        print("\n【检测结果】: 未发现明显的改写攻击特征")

    print("\n" + "-"*60)
    print("详细分析")
    print("-"*60)

    # 词汇多样性
    vocab = results['details']['vocabulary_diversity']
    print(f"\n1. 词汇多样性:")
    print(f"   - 词汇丰富度: {vocab['ratio']:.2%}")
    print(f"   - 独特词汇: {vocab.get('unique_words', 0)}")
    print(f"   - 总词汇: {vocab.get('total_words', 0)}")
    print(f"   - 判断: {vocab['reason']}")

    # 句子结构
    structure = results['details']['structure_consistency']
    print(f"\n2. 句子结构一致性:")
    print(f"   - 平均长度: {structure.get('mean_length', 0):.1f}字")
    print(f"   - 标准差: {structure.get('std_dev', 0):.2f}")
    print(f"   - 长度范围: {structure.get('min_length', 0)}-{structure.get('max_length', 0)}字")
    print(f"   - 判断: {structure['reason']}")

    # 改写痕迹
    marks = results['details']['paraphrasing_marks']
    print(f"\n3. 改写痕迹:")
    print(f"   - 发现数量: {marks['count']}处")
    if marks['patterns']:
        print(f"   - 典型模式:")
        for pattern in marks['patterns'][:5]:
            print(f"     · {pattern}")

    # 个人声音
    voice = results['details']['personal_voice']
    print(f"\n4. 个人表达特征:")
    print(f"   - 个人声音: {'✓' if voice['has_personal_voice'] else '✗'}")
    print(f"   - 数据引用: {'✓' if voice.get('has_data') else '✗'}")
    print(f"   - 转折表达: {'✓' if voice.get('has_contrast') else '✗'}")

    print("\n" + "="*60)

    # 建议
    if results['paraphrasing_probability'] >= 0.5:
        print("\n【修改建议】:")
        print("1. 加入个人观点和表达（'我认为'、'笔者'等）")
        print("2. 使用具体数据代替空话")
        print("3. 增加句子长度的自然变化")
        print("4. 加入转折、意外等逻辑连接")
        print("5. 避免过于标准化的表达方式")
        print("\n建议: 用自己的话重新表达核心观点，而不是依赖改写工具")
    else:
        print("\n【结论】: 文本表现自然，未发现明显的改写工具使用痕迹")

    print("="*60 + "\n")


def main():
    """主函数"""
    import sys

    if len(sys.argv) > 1:
        # 从文件读取
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            text = f.read()
    else:
        # 示例文本
        text = """
        本文采用问卷调查方式对大学生网络使用行为进行了调查。
        分析发现，上网时间越长的同学，成绩往往越低。
        这个发现对学校的教育工作有参考价值。

        通过使用标准方法，我们对数据进行了收集。
        研究显示，网络使用对学习成绩有重要影响。
        这项研究对于教育管理具有关键意义。
        """

    detector = ParaphrasingDetector()
    results = detector.detect(text)
    print_report(text, results)


if __name__ == '__main__':
    main()
