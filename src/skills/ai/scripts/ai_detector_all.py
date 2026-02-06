#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI文本检测工具集 - 统一入口

整合所有AI文本检测方法:
1. detect_vocabulary - AI词汇密度检测
2. detect_burstiness - 句式突发性检测
3. detect_paraphrasing - 改写攻击检测
4. detect_abstract - 摘要专用检测
5. detect_comprehensive - 综合检测
6. batch_detect - 批量检测

使用方法:
    # 词汇密度检测
    python ai_detector_all.py vocabulary 文件.txt

    # 句式突发性检测
    python ai_detector_all.py burstiness 文件.txt

    # 改写攻击检测
    python ai_detector_all.py paraphrasing 文件.txt

    # 摘要检测
    python ai_detector_all.py abstract "摘要内容"
    python ai_detector_all.py abstract -f 文件.txt

    # 综合检测
    python ai_detector_all.py comprehensive 文件.txt

    # 批量检测
    python ai_detector_all.py batch file1.txt file2.txt
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List

try:
    import jieba
    import numpy as np
    HAS_JIEBA = True
    HAS_NUMPY = True
except ImportError:
    HAS_JIEBA = 'jieba' in sys.modules
    HAS_NUMPY = 'numpy' in sys.modules


# ============================================================================
# AI词汇库定义
# ============================================================================

AI_WORDS = {
    # 连接词/过渡词
    "此外", "同时", "另外", "再者", "总体而言", "综上所述", "总的来说",
    "而且", "并且", "进而", "从而", "首先", "其次", "最后",
    "一方面", "另一方面", "除此之外", "另外一方面",
    # 形容词/副词
    "重要的", "关键的", "核心的", "显著的", "深刻的", "全面的", "系统的",
    "基本的", "主要的", "本质的", "根本的", "重大的",
    "具有", "关键", "重要",
    # 动词
    "促进", "推动", "助力", "支撑", "增强", "提升",
    "体现", "反映", "展现", "表明", "涵盖", "包含", "涉及", "覆盖",
    "强调", "突出", "彰显", "凸显",
    # 虚词
    "具有重要", "具有重要理论", "具有重要实践", "具有重要的",
    "提供参考", "具有重要的参考价值", "重要参考",
    "具有一定的", "具有重要意义",
    # 其他
    "深入分析", "详细分析", "全面分析", "综合分析",
    "关键因素", "核心因素", "主要因素",
    "理论意义", "实践意义",
    "值得关注", "值得注意", "需要指出"
}

AI_VOCAB = {
    'connection': [
        '此外', '同时', '另外', '再者', '总体而言', '综上所述',
        '而且', '并且', '进而', '从而', '首先', '其次', '最后',
        '一方面', '另一方面', '另外', '再次', '除此之外', '另外一方面'
    ],
    'adjective': [
        '重要的', '关键的', '核心的', '显著的', '深刻的', '基本的',
        '主要的', '本质的', '根本的', '重大的', '重要的', '具有',
        '关键', '重要'
    ],
    'verb': [
        '体现', '反映', '展现', '表明', '涵盖', '包含', '包括',
        '促进', '推动', '助力', '提升', '改善', '增强',
        '具有一定的', '具有重要意义', '具有重要的', '提供参考'
    ],
    'formula': [
        '具有重要', '提供参考', '具有重要意义',
        '具有重要的', '具有一定的', '起到了一定的'
    ]
}

FORMULA_STARTS = [
    r'^本文.*?(采用|使用|利用|通过)',
    r'^本研究.*?(采用|使用|利用|通过)',
    r'^本研究.*?(旨在|在于|关注)',
    r'^文章.*?(分析|探讨|研究)',
    r'从.*层面来看',
    r'从.*方面来看',
    r'总体而言',
    r'综上所述',
]

AI_PATTERNS = [
    r'一方面.*?另一方面',
    r'首先.*?其次.*?最后',
    r'重要.*?意义',
    r'关键.*?作用',
    r'显著.*?影响',
    r'具有.*?性',
    r'研究表明.*?(，|。)',
    r'学者认为.*?(，|。)',
]

PARAPHRASE_MARKERS = {
    '采用': ['使用', '利用', '应用'],
    '使用': ['采用', '利用', '运用'],
    '分析': ['探讨', '研究', '探究'],
    '表明': ['显示', '揭示', '展现'],
    '包含': ['包括', '涵盖', '含有'],
}


# ============================================================================
# 1. AI词汇密度检测
# ============================================================================

def detect_vocabulary(text: str) -> Dict:
    """
    检测文本的AI词汇密度

    Args:
        text: 待检测文本

    Returns:
        检测结果字典
    """
    word_count = len(text.split())
    char_count = len(text)

    ai_count = 0
    found_words = []
    text_lower = text.lower()
    words_to_check = {word.lower(): word for word in AI_WORDS}

    for word_lower, original in words_to_check.items():
        pattern = r'\b' + re.escape(word_lower) + r'\b'
        matches = re.findall(pattern, text_lower)
        if matches:
            count = len(matches)
            ai_count += count
            found_words.extend([original] * count)

    density_per_1000 = (ai_count / char_count * 1000) if char_count > 0 else 0

    if density_per_1000 > 50:
        risk = "高风险"
        risk_color = "🔴"
    elif density_per_1000 > 30:
        risk = "中等风险"
        risk_color = "🟡"
    else:
        risk = "正常"
        risk_color = "🟢"

    return {
        'total_chars': char_count,
        'total_words': word_count,
        'ai_count': ai_count,
        'density_per_1000': round(density_per_1000, 1),
        'risk_level': risk,
        'risk_color': risk_color,
        'found_words': found_words
    }


# ============================================================================
# 2. 句式突发性检测
# ============================================================================

def split_sentences(text: str) -> List[str]:
    """分割句子"""
    sentences = re.split(r'[。！？；]', text)
    return [s.strip() for s in sentences if 5 < len(s.strip()) < 200]


def detect_burstiness(text: str) -> Dict:
    """
    检测文本的句式突发性

    Args:
        text: 待检测文本

    Returns:
        突发性分析结果
    """
    sentences = split_sentences(text)

    if len(sentences) < 5:
        return {
            'sentence_count': len(sentences),
            'mean_length': 0,
            'std_dev': 0,
            'min_length': 0,
            'max_length': 0,
            'cv': 0,
            'adjacent_diff': 0,
            'risk_level': '数据不足',
            'risk_color': '⚪',
            'reason': '句子数量太少(少于5句),无法准确评估'
        }

    lengths = [len(s) for s in sentences]

    if HAS_NUMPY:
        mean_length = float(np.mean(lengths))
        std_dev = float(np.std(lengths))
    else:
        mean_length = sum(lengths) / len(lengths)
        variance = sum((x - mean_length) ** 2 for x in lengths) / len(lengths)
        std_dev = variance ** 0.5

    min_length = min(lengths)
    max_length = max(lengths)
    cv = std_dev / mean_length if mean_length > 0 else 0

    adjacent_diffs = [abs(lengths[i] - lengths[i+1]) for i in range(len(lengths)-1)]
    avg_adjacent_diff = sum(adjacent_diffs) / len(adjacent_diffs) if adjacent_diffs else 0

    if cv < 0.15:
        risk = "高风险"
        risk_color = "🔴"
        reason = f"句子长度过于一致(变异系数{cv:.3f}),缺乏自然变化"
    elif cv < 0.25:
        risk = "中等风险"
        risk_color = "🟡"
        reason = f"句子长度变化较小(变异系数{cv:.3f}),建议增加变化"
    else:
        risk = "正常"
        risk_color = "🟢"
        reason = f"句子长度变化自然(变异系数{cv:.3f})"

    return {
        'sentence_count': len(sentences),
        'mean_length': round(mean_length, 1),
        'std_dev': round(std_dev, 2),
        'min_length': min_length,
        'max_length': max_length,
        'cv': round(cv, 3),
        'adjacent_diff': round(avg_adjacent_diff, 1),
        'length_range': max_length - min_length,
        'risk_level': risk,
        'risk_color': risk_color,
        'reason': reason
    }


# ============================================================================
# 3. 改写攻击检测
# ============================================================================

def detect_paraphrasing(text: str) -> Dict:
    """
    检测文本的改写攻击痕迹

    Args:
        text: 待检测文本

    Returns:
        改写攻击检测结果
    """
    issues = []

    # 1. 词汇多样性
    if HAS_JIEBA:
        words = list(jieba.cut(text))
        words = [w for w in words if len(w) > 1 and w.strip()]
        unique_ratio = len(set(words)) / len(words) if words else 0
    else:
        unique_ratio = 0
        issues.append("缺少依赖包(jieba)")

    # 2. 句子结构一致性
    sentences = split_sentences(text)
    if len(sentences) >= 5:
        lengths = [len(s) for s in sentences]
        if HAS_NUMPY:
            std_dev = float(np.std(lengths))
        else:
            mean_len = sum(lengths) / len(lengths)
            variance = sum((x - mean_len) ** 2 for x in lengths) / len(lengths)
            std_dev = variance ** 0.5

        if std_dev < 10:
            issues.append("句子结构过于一致")
    else:
        issues.append("句子数量不足")

    # 3. 改写痕迹
    paraphrase_count = 0
    paraphrase_examples = []

    for original, alternatives in PARAPHRASE_MARKERS.items():
        if original in text:
            for alt in alternatives:
                if alt in text:
                    paraphrase_count += 1
                    paraphrase_examples.append(f"{original} → {alt}")
                    break

    if paraphrase_count > 0:
        issues.append(f"发现{paraphrase_count}处改写痕迹")

    # 4. 个人表达特征
    personal_features = []
    if '我认为' in text or '笔者' in text or '我们' in text:
        personal_features.append('个人声音')
    if re.search(r'\d+.*?%|\d+.*?个|\d+.*?例', text):
        personal_features.append('数据引用')
    if '但是' in text or '然而' in text or '不过' in text:
        personal_features.append('转折表达')

    if len(personal_features) < 2:
        issues.append("缺乏个人表达特征")

    # 计算风险
    risk_score = len(issues) / 4
    if risk_score >= 0.6:
        risk = "高风险"
        risk_color = "🔴"
    elif risk_score >= 0.3:
        risk = "中等风险"
        risk_color = "🟡"
    else:
        risk = "低风险"
        risk_color = "🟢"

    return {
        'risk_level': risk,
        'risk_color': risk_color,
        'risk_score': risk_score,
        'issues': issues,
        'paraphrase_count': paraphrase_count,
        'paraphrase_examples': paraphrase_examples,
        'unique_ratio': unique_ratio
    }


# ============================================================================
# 4. 摘要专用检测
# ============================================================================

def detect_abstract(text: str) -> Dict:
    """
    针对摘要的AI率检测

    Args:
        text: 摘要文本

    Returns:
        摘要检测结果
    """
    issues = []
    word_count = len(text)

    # 1. 检查公式化开头
    if text.startswith('本文') or text.startswith('本研究'):
        issues.append("公式化开头：'本文'/'本研究'开头")

    # 2. AI词汇密度
    ai_count = sum(text.count(word) for word in AI_WORDS)
    density = (ai_count / word_count * 100) if word_count > 0 else 0

    if density > 5:
        issues.append(f"AI词汇密度高: {density:.1f}%")

    # 3. 检查套话
    cliches = [
        '具有重要的理论意义和实践意义',
        '具有一定的参考价值',
        '为相关研究提供参考'
    ]
    for cliche in cliches:
        if cliche in text:
            issues.append(f"套话虚词: '{cliche}'")
            break

    # 4. 检查是否有具体数据
    has_data = bool(re.search(r'\d+', text))
    if not has_data:
        issues.append("缺乏具体数据")

    # 计算AI概率
    ai_probability = len(issues) * 20

    if ai_probability >= 60:
        risk = "高风险"
        risk_color = "🔴"
    elif ai_probability >= 40:
        risk = "中等风险"
        risk_color = "🟡"
    else:
        risk = "低风险"
        risk_color = "🟢"

    return {
        'word_count': word_count,
        'ai_count': ai_count,
        'density': round(density, 1),
        'ai_probability': min(ai_probability, 100),
        'risk_level': risk,
        'risk_color': risk_color,
        'issues': issues,
        'has_data': has_data
    }


# ============================================================================
# 5. 综合检测
# ============================================================================

def detect_comprehensive(text: str) -> Dict:
    """
    综合AI检测

    Args:
        text: 待检测文本

    Returns:
        综合检测结果
    """
    results = {
        'overall_score': 0.0,
        'risk_level': 'unknown',
        'tests': {}
    }

    # 测试1: AI词汇密度
    vocab_result = _test_vocabulary_density(text)
    results['tests']['vocabulary_density'] = vocab_result

    # 测试2: 句式突发性
    burstiness_result = _test_burstiness(text)
    results['tests']['burstiness'] = burstiness_result

    # 测试3: 公式化结构
    formula_result = _test_formulaic_structure(text)
    results['tests']['formulaic_structure'] = formula_result

    # 测试4: 模式识别
    pattern_result = _test_patterns(text)
    results['tests']['patterns'] = pattern_result

    # 测试5: 句子均匀度
    uniformity_result = _test_sentence_uniformity(text)
    results['tests']['sentence_uniformity'] = uniformity_result

    # 计算总分
    weights = {
        'vocabulary_density': 0.3,
        'burstiness': 0.25,
        'formulaic_structure': 0.2,
        'patterns': 0.15,
        'sentence_uniformity': 0.1
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


def _test_vocabulary_density(text: str) -> Dict:
    """测试: AI词汇密度"""
    all_ai_words = []
    for category in AI_VOCAB.values():
        all_ai_words.extend(category)

    ai_word_count = sum(text.count(word) for word in all_ai_words)
    total_chars = len(text)
    density = (ai_word_count / total_chars * 1000) if total_chars > 0 else 0

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


def _test_burstiness(text: str) -> Dict:
    """测试: 句式突发性"""
    sentences = split_sentences(text)

    if len(sentences) < 5:
        return {'score': 0.0, 'level': '数据不足', 'reason': '句子数量太少'}

    lengths = [len(s) for s in sentences]

    if HAS_NUMPY:
        mean_len = float(np.mean(lengths))
        std_dev = float(np.std(lengths))
    else:
        mean_len = sum(lengths) / len(lengths)
        variance = sum((x - mean_len) ** 2 for x in lengths) / len(lengths)
        std_dev = variance ** 0.5

    cv = std_dev / mean_len if mean_len > 0 else 0

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
        'min_length': min(lengths),
        'max_length': max(lengths),
        'reason': reason
    }


def _test_formulaic_structure(text: str) -> Dict:
    """测试: 公式化结构"""
    paragraphs = text.split('\n')
    paragraphs = [p.strip() for p in paragraphs if len(p.strip()) > 20]

    formula_count = 0
    total_sentences = 0

    for para in paragraphs:
        sentences = re.split(r'[。！？]', para)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 5]

        for sent in sentences:
            total_sentences += 1
            for pattern in FORMULA_STARTS:
                if re.match(pattern, sent):
                    formula_count += 1
                    break

    vague_refs = len(re.findall(r'(研究表明|学者认为|学者指出|研究显示)(?=，|。)', text))
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


def _test_patterns(text: str) -> Dict:
    """测试: 模式识别"""
    pattern_counts = {}

    for pattern in AI_PATTERNS:
        matches = len(re.findall(pattern, text, re.DOTALL))
        pattern_counts[pattern] = matches

    total = sum(pattern_counts.values())
    normalized_score = min(total / len(text) * 500, 1.0)

    if normalized_score > 0.6:
        score = 1.0
        level = '高风险'
    elif normalized_score > 0.3:
        score = 0.5
        level = '中风险'
    else:
        score = 0.1
        level = '安全'

    return {
        'score': score,
        'level': level,
        'pattern_counts': pattern_counts,
        'total_count': total
    }


def _test_sentence_uniformity(text: str) -> Dict:
    """测试: 句子均匀度"""
    sentences = split_sentences(text)

    if len(sentences) < 10:
        return {'score': 0.0, 'level': '数据不足'}

    lengths = [len(s) for s in sentences]
    diffs = [abs(lengths[i] - lengths[i+1]) for i in range(len(lengths)-1)]
    avg_diff = sum(diffs) / len(diffs)

    if avg_diff < 10:
        score = 1.0
        level = '高风险'
        reason = '相邻句子长度差异过小'
    elif avg_diff < 20:
        score = 0.5
        level = '中风险'
        reason = '相邻句子长度差异较小'
    else:
        score = 0.1
        level = '安全'
        reason = '相邻句子长度差异自然'

    return {
        'score': score,
        'level': level,
        'avg_diff': avg_diff,
        'min_diff': min(diffs),
        'max_diff': max(diffs),
        'reason': reason
    }


# ============================================================================
# 6. 批量检测
# ============================================================================

def batch_detect(file_paths: List[str], output_json: str = None) -> List[Dict]:
    """
    批量检测多个文件

    Args:
        file_paths: 文件路径列表
        output_json: 输出JSON文件路径(可选)

    Returns:
        检测结果列表
    """
    results = []

    for filepath in file_paths:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                text = f.read()

            result = {
                'file': filepath,
                'result': detect_comprehensive(text)
            }
            results.append(result)

            print(f"✅ {filepath}: {result['result']['risk_level']} ({result['result']['overall_score']:.1%})")

        except Exception as e:
            print(f"❌ {filepath}: 读取失败 - {e}")
            results.append({'file': filepath, 'error': str(e)})

    if output_json:
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 结果已保存到: {output_json}")

    return results


# ============================================================================
# 报告打印函数
# ============================================================================

def print_vocabulary_report(result: Dict):
    """打印词汇密度报告"""
    print("\n" + "="*60)
    print("AI词汇密度检测报告")
    print("="*60)
    print(f"\n总字符数: {result['total_chars']}")
    print(f"总词数: {result['total_words']}")
    print(f"AI词汇数量: {result['ai_count']}")
    print(f"AI词汇密度: {result['density_per_1000']} 个/1000字")
    print(f"\n风险等级: {result['risk_color']} {result['risk_level']}")

    if result['found_words']:
        word_counts = Counter(result['found_words'])
        top_words = word_counts.most_common(10)
        print(f"\n检测到的高频AI词汇 (前10个):")
        for word, count in top_words:
            print(f"  - {word}: {count}次")

    print("\n" + "="*60)


def print_burstiness_report(result: Dict):
    """打印突发性报告"""
    print("\n" + "="*60)
    print("句式突发性检测报告")
    print("="*60)
    print(f"\n📊 基本统计:")
    print(f"   总句子数: {result['sentence_count']}")
    print(f"   平均长度: {result['mean_length']} 字")
    print(f"   长度范围: {result['min_length']}-{result['max_length']} 字")
    print(f"\n📈 突发性指标:")
    print(f"   标准差: {result['std_dev']} 字")
    print(f"   变异系数(CV): {result['cv']}")
    print(f"\n🎯 风险评估:")
    print(f"   风险等级: {result['risk_color']} {result['risk_level']}")
    print(f"   判断依据: {result['reason']}")
    print("\n" + "="*60)


def print_paraphrasing_report(result: Dict, text: str):
    """打印改写攻击报告"""
    print("\n" + "="*60)
    print("改写攻击检测报告")
    print("="*60)
    print(f"\n【风险等级】: {result['risk_color']} {result['risk_level']}")
    print(f"【改写概率】: {result['risk_score']:.1%}")

    if result['issues']:
        print(f"\n【检测到的问题】:")
        for i, issue in enumerate(result['issues'], 1):
            print(f"  {i}. {issue}")

    print("\n" + "="*60)


def print_abstract_report(result: Dict):
    """打印摘要检测报告"""
    print("\n" + "="*60)
    print("摘要AI率检测报告")
    print("="*60)
    print(f"\n摘要字数: {result['word_count']}")
    print(f"AI词汇数量: {result['ai_count']}")
    print(f"AI词汇密度: {result['density']}% (每100字)")
    print(f"\nAI概率评估: {result['ai_probability']}%")
    print(f"风险等级: {result['risk_color']} {result['risk_level']}")

    if result['issues']:
        print(f"\n检测结果:")
        for issue in result['issues']:
            marker = "❌" if any(x in issue for x in ["公式化", "套话", "密度高", "缺乏"]) else "✓"
            print(f"  {marker} {issue}")

    print("\n" + "="*60)


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
        'patterns': '模式识别',
        'sentence_uniformity': '句子均匀度'
    }

    for key, name in test_names.items():
        test = results['tests'][key]
        print(f"\n{name}:")
        print(f"  风险等级: {test['level']}")
        print(f"  得分: {test['score']:.2f}/1.00")

    print("\n" + "="*70)
    score = results['overall_score']
    if score >= 0.7:
        print("\n【严重警告】文本表现出强烈的AI生成特征")
    elif score >= 0.5:
        print("\n【警告】文本可能包含AI生成内容")
    elif score >= 0.3:
        print("\n【注意】文本存在轻微AI特征")
    else:
        print("\n【良好】文本未表现出明显AI特征")
    print("="*70 + "\n")


# ============================================================================
# 主函数
# ============================================================================

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="AI文本检测工具集 - 统一入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
检测类型:
  vocabulary      AI词汇密度检测
  burstiness      句式突发性检测
  paraphrasing    改写攻击检测
  abstract        摘要专用检测
  comprehensive   综合检测
  batch           批量检测

示例:
  %(prog)s vocabulary file.txt
  %(prog)s burstiness file.txt
  %(prog)s paraphrasing file.txt
  %(prog)s abstract "摘要内容"
  %(prog)s abstract -f file.txt
  %(prog)s comprehensive file.txt
  %(prog)s batch file1.txt file2.txt -o result.json
        """
    )

    parser.add_argument('detector_type', metavar='TYPE',
                       choices=['vocabulary', 'burstiness', 'paraphrasing',
                               'abstract', 'comprehensive', 'batch'],
                       help='检测类型')

    parser.add_argument('inputs', nargs='+', help='输入文件或文本')

    parser.add_argument('-f', '--file', action='store_true',
                       help='从文件读取(用于abstract检测)')

    parser.add_argument('-o', '--output', help='输出JSON文件(用于batch检测)')

    args = parser.parse_args()

    # 检查依赖
    if not HAS_JIEBA or not HAS_NUMPY:
        print("⚠️  警告: 缺少依赖包")
        if not HAS_JIEBA:
            print("   - jieba")
        if not HAS_NUMPY:
            print("   - numpy")
        print("   部分功能将受限,建议安装: pip install jieba numpy")
        print()

    # 根据检测类型执行
    if args.detector_type == 'vocabulary':
        filepath = args.inputs[0]
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
        result = detect_vocabulary(text)
        print_vocabulary_report(result)

    elif args.detector_type == 'burstiness':
        filepath = args.inputs[0]
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
        result = detect_burstiness(text)
        print_burstiness_report(result)

    elif args.detector_type == 'paraphrasing':
        filepath = args.inputs[0]
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
        result = detect_paraphrasing(text)
        print_paraphrasing_report(result, text)

    elif args.detector_type == 'abstract':
        if args.file:
            # 从文件读取
            with open(args.inputs[0], 'r', encoding='utf-8') as f:
                text = f.read()
        else:
            # 直接使用文本
            text = args.inputs[0]
        result = detect_abstract(text)
        print_abstract_report(result)

    elif args.detector_type == 'comprehensive':
        filepath = args.inputs[0]
        with open(filepath, 'r', encoding='utf-8') as f:
            text = f.read()
        result = detect_comprehensive(text)
        print_comprehensive_report(result)

    elif args.detector_type == 'batch':
        batch_detect(args.inputs, args.output)


if __name__ == '__main__':
    main()
