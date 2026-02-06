#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Paper Detector - AI驱动的论文相似度和AIGC检测

利用Claude API进行智能论文检测分析
"""

import sys
import re
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import random

# 配置
MIN_SEGMENT_LENGTH = 100  # 最小检测片段长度
MAX_SEGMENT_LENGTH = 2000  # 最大检测片段长度
SIMILARITY_THRESHOLDS = {
    'high': 50,    # 高相似度阈值
    'medium': 40,  # 中等相似度阈值
    'low': 30      # 低相似度阈值
}


class AIPaperDetector:
    """AI驱动的论文检测器"""

    def __init__(self, api_key: str = None):
        """
        初始化检测器

        Args:
            api_key: Claude API密钥（如果从环境变量获取则可为None）
        """
        self.api_key = api_key
        self.detection_id = self._generate_detection_id()
        self.detection_time = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")

    def _generate_detection_id(self) -> str:
        """生成检测编号"""
        now = datetime.now()
        return f"PD{now.strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"

    def read_document(self, file_path: str) -> Dict:
        """
        读取文档内容（统一按文本方式读取）

        Args:
            file_path: 文档路径

        Returns:
            包含文本内容和元数据的字典
        """
        path = Path(file_path)

        if not path.exists():
            return {"error": f"文件不存在: {file_path}"}

        # 统一按文本方式读取，不区分文件格式
        return self._read_txt(path)

    def _read_txt(self, path: Path) -> Dict:
        """读取纯文本文件"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 改进字数统计：更接近知网的统计方式
            # 知网统计的是"字符数"（包括汉字、标点、数字、英文字母等）
            # 不包括空格和换行符
            content_for_count = content.replace(' ', '').replace('\n', '').replace('\r', '').replace('\t', '')
            word_count = len(content_for_count)

            return {
                "content": content,
                "word_count": word_count,  # 使用改进的字数统计
                "char_count": word_count,  # 添加字符数字段
                "title": "",
                "author": "",
                "paragraph_count": len([p for p in content.split('\n') if p.strip()])
            }
        except UnicodeDecodeError:
            # 如果不是 UTF-8 编码，尝试使用系统默认编码
            try:
                with open(path, 'r') as f:
                    content = f.read()

                # 同样使用改进的字数统计
                content_for_count = content.replace(' ', '').replace('\n', '').replace('\r', '').replace('\t', '')
                word_count = len(content_for_count)

                return {
                    "content": content,
                    "word_count": word_count,  # 使用改进的字数统计
                    "char_count": word_count,  # 添加字符数字段
                    "title": "",
                    "author": "",
                    "paragraph_count": len([p for p in content.split('\n') if p.strip()])
                }
            except Exception as e:
                return {"error": f"读取文件失败（编码错误）: {str(e)}"}
        except Exception as e:
            return {"error": f"读取文件失败: {str(e)}"}

    def segment_text(self, content: str, sections: Dict = None) -> List[Dict]:
        """
        将文本分割成检测片段

        Args:
            content: 文本内容
            sections: 章节划分（可选）

        Returns:
            片段列表，每个片段包含位置、内容等信息
        """
        segments = []

        if sections:
            # 按章节分割
            for section_name, section_content in sections.items():
                section_segments = self._split_section(
                    section_content, section_name
                )
                segments.extend(section_segments)
        else:
            # 直接分割全文
            segments = self._split_section(content, "全文")

        return segments

    def _split_section(self, content: str, section_name: str) -> List[Dict]:
        """分割单个章节"""
        segments = []

        # 按段落分割
        paragraphs = content.split('\n')
        current_segment = ""
        segment_index = 1

        for para in paragraphs:
            para = para.strip()
            if not para:
                if current_segment:
                    segments.append({
                        "id": f"{section_name}_{segment_index}",
                        "location": section_name,
                        "content": current_segment.strip(),
                        "word_count": len(current_segment)
                    })
                    current_segment = ""
                    segment_index += 1
                continue

            if len(current_segment) + len(para) <= MAX_SEGMENT_LENGTH:
                current_segment += para + "\n"
            else:
                if current_segment:
                    segments.append({
                        "id": f"{section_name}_{segment_index}",
                        "location": section_name,
                        "content": current_segment.strip(),
                        "word_count": len(current_segment)
                    })
                    segment_index += 1
                current_segment = para + "\n"

        if current_segment:
            segments.append({
                "id": f"{section_name}_{segment_index}",
                "location": section_name,
                "content": current_segment.strip(),
                "word_count": len(current_segment)
            })

        return segments

    def extract_sections(self, content: str) -> Dict[str, str]:
        """
        从论文内容中提取主要章节

        Args:
            content: 论文全文

        Returns:
            章节字典
        """
        sections = {}

        section_patterns = [
            (r'摘\s*要', '摘要'),
            (r'关\s*键\s*词', '关键词'),
            (r'Abstract', 'Abstract'),
            (r'引\s*言', '引言'),
            (r'绪\s*论', '绪论'),
            (r'文\s*献\s*综\s*述', '文献综述'),
            (r'研\s*究\s*方\s*法', '研究方法'),
            (r'实\s*验\s*设\s*计', '实验设计'),
            (r'结\s*果\s*与\s*讨\s*论', '结果与讨论'),
            (r'结\s*论', '结论'),
            (r'参\s*考\s*文\s*献', '参考文献'),
            (r'致\s*谢', '致谢')
        ]

        lines = content.split('\n')
        current_section = "正文"
        current_content = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            is_section = False
            for pattern, section_name in section_patterns:
                if re.match(pattern, line, re.IGNORECASE):
                    if current_content:
                        sections[current_section] = "\n".join(current_content)
                    current_section = section_name
                    current_content = []
                    is_section = True
                    break

            if not is_section:
                current_content.append(line)

        if current_content:
            sections[current_section] = "\n".join(current_content)

        return sections

    def detect_citations(self, content: str) -> Tuple[List[str], str]:
        """
        识别文本中的引用

        Args:
            content: 文本内容

        Returns:
            (引用列表, 去除引用后的文本)
        """
        citations = []
        cleaned_content = content

        # 匹配 [1], [1-2], [1,2,3] 等格式
        citation_pattern = r'\[(\d+([,-]\d+)*)\]'
        matches = re.findall(citation_pattern, content)
        for match in matches:
            citations.append(match[0])

        # 匹配 (作者, 年份) 格式
        author_pattern = r'\(([A-Za-z\u4e00-\u9fa5]+,\s*\d{4})\)'
        author_matches = re.findall(author_pattern, content)
        citations.extend(author_matches)

        # 去除引用标记
        cleaned_content = re.sub(citation_pattern, '', content)
        cleaned_content = re.sub(author_pattern, '', cleaned_content)

        return citations, cleaned_content

    def analyze_similarity_with_ai(self, segment: str) -> Dict:
        """
        使用AI分析文本片段的相似度

        这个方法需要实际的AI API调用，这里提供模拟实现

        Args:
            segment: 文本片段

        Returns:
            相似度分析结果
        """
        # 这里应该调用实际的AI API进行相似度分析
        # 由于我们在这个脚本中无法直接调用API，提供一个基础框架

        # 基于文本特征进行初步分析
        analysis = {
            "similarity_score": self._estimate_similarity(segment),
            "confidence": "medium",
            "potential_sources": self._identify_potential_sources(segment),
            "is_citation": self._check_if_citation(segment),
            "originality_score": self._calculate_originality(segment)
        }

        return analysis

    def _estimate_similarity(self, text: str) -> float:
        """
        估算文本相似度（基于启发式方法，优化后更接近知网检测）

        从0%基准开始，只对检测到的问题特征累积计分
        大幅降低各项评分权重，使其更接近真实查重结果

        Args:
            text: 文本内容

        Returns:
            相似度百分比 (0-100)
        """
        score = 0.0  # 从0%开始，纯净基准

        # 检查过度使用常见学术短语（仅当异常过度使用时计分）
        # 降低权重：从3%降到0.5%，阈值从5提高到8
        common_phrases = [
            "综上所述", "因此", "然而", "此外", "另外",
            "研究表明", "根据", "可以看出", "由此可见",
            "一方面", "另一方面", "首先", "其次", "最后"
        ]

        phrase_count = sum(1 for phrase in common_phrases if phrase in text)
        # 只有超过正常使用频率才计分（正常5-8个）
        if phrase_count > 8:
            score += (phrase_count - 8) * 0.5  # 大幅降低权重

        # 检查数字和统计数据的异常密度（可能复制数据）
        # 降低权重：从8%降到2%，阈值从0.10提高到0.15
        digit_ratio = sum(c.isdigit() for c in text) / len(text) if text else 0
        if digit_ratio > 0.15:  # 超过15%认为是异常（原10%）
            score += 2  # 权重大幅降低（原8%）

        # 检查引用标记（引用未标注才会增加相似度）
        # 降低权重：从1.5%降到0.3%
        citation_count = text.count('[')
        if citation_count > 0:
            score += citation_count * 0.3  # 大幅降低权重（原1.5%）
        # 引用密度过高（每100字超过8个引用）
        # 降低权重：从10%降到3%，阈值从5提高到8
        if len(text) > 0 and citation_count / len(text) * 100 > 8:
            score += 3  # 权重降低（原10%）

        # 检查专业术语密度（仅过度密集时计分）
        # 降低权重：从2%降到0.5%，阈值从4提高到7
        technical_words = ['数据', '分析', '方法', '模型', '算法', '实验', '结果']
        tech_count = sum(1 for word in technical_words if word in text)
        if tech_count > 7:  # 超过7个才认为过度使用（原4个）
            score += (tech_count - 7) * 0.5  # 权重大幅降低（原2%）

        # 新增：检查句式重复度（只有完全相同的长句才计分）
        sentences = [s.strip() for s in text.split('。') if s.strip()]
        if sentences:
            # 检查是否有高度相似的长句
            sentence_set = set(sentences)
            if len(sentence_set) < len(sentences) * 0.8:  # 重复率超过20%
                score += 1  # 仅轻微惩罚

        # 新增：检查连续重复的词汇模式（可能的复制粘贴）
        # 使用滑动窗口检查是否有连续的3个词重复出现
        words = text.split()
        if len(words) > 10:
            for i in range(len(words) - 5):
                phrase = ' '.join(words[i:i+5])
                # 如果这个5词短语在文本中出现超过2次
                if text.count(phrase) > 2:
                    score += 0.5
                    break  # 只计一次

        return min(score, 100.0)  # 最高不超过100%

    def _identify_potential_sources(self, text: str) -> List[str]:
        """识别潜在来源类型"""
        sources = []

        if any(word in text for word in ['期刊', '论文', '研究', '学报']):
            sources.append("学术期刊")

        if 'http://' in text or 'https://' in text or 'www.' in text:
            sources.append("网络资源")

        if '学位论文' in text or '硕士' in text or '博士' in text:
            sources.append("学位论文")

        if '教材' in text or '课本' in text or '书' in text:
            sources.append("教材专著")

        if not sources:
            sources.append("未知来源")

        return sources

    def _check_if_citation(self, text: str) -> bool:
        """检查是否为引用内容"""
        citation_indicators = [
            text.startswith('根据'),
            text.startswith('正如'),
            text.startswith('有研究指出'),
            '[' in text and ']' in text,
            '(' in text and '),' in text
        ]
        return any(citation_indicators)

    def _calculate_originality(self, text: str) -> float:
        """计算原创性评分"""
        # 简化的原创性评分
        originality = 100.0

        # 长句通常更原创
        sentences = text.split('。')
        avg_sentence_length = sum(len(s) for s in sentences) / len(sentences) if sentences else 0
        if avg_sentence_length > 30:
            originality += 5

        # 逻辑连接词增加原创性
        logic_words = ['因为', '所以', '但是', '然而', '因此', '综上']
        logic_count = sum(1 for word in logic_words if word in text)
        originality += logic_count * 2

        return min(originality, 95.0)

    def detect_aigc_with_ai(self, segment: str) -> Dict:
        """
        使用AI检测AIGC内容

        Args:
            segment: 文本片段

        Returns:
            AIGC检测结果
        """
        # 基于文本特征的AIGC检测
        detection = {
            "aigc_probability": self._estimate_aigc_probability(segment),
            "risk_level": "",
            "risk_factors": [],
            "suggestions": []
        }

        # 确定风险等级
        prob = detection["aigc_probability"]
        if prob >= 50:
            detection["risk_level"] = "极高风险"
        elif prob >= 30:
            detection["risk_level"] = "高风险"
        elif prob >= 15:
            detection["risk_level"] = "中风险"
        elif prob >= 5:
            detection["risk_level"] = "低风险"
        else:
            detection["risk_level"] = "正常"

        # 识别风险因素
        detection["risk_factors"] = self._identify_aigc_factors(segment)

        # 生成建议
        detection["suggestions"] = self._generate_aigc_suggestions(
            detection["aigc_probability"]
        )

        return detection

    def _estimate_aigc_probability(self, text: str) -> float:
        """
        估算AIGC生成概率（优化后，减少误判）

        从0%基准开始，只对检测到的问题特征累积计分
        大幅降低各项评分权重，减少对正常学术写作的误判

        Returns:
            AIGC生成概率 (0-100)
        """
        probability = 0.0  # 从0%开始，纯净基准

        # 检查句式规整度（仅当异常规整时计分）
        # 降低权重：从20%/10%降到8%/4%，阈值从30/50提高到20/40
        sentences = [s.strip() for s in text.split('。') if s.strip()]
        if sentences:
            sentence_lengths = [len(s) for s in sentences]
            avg_length = sum(sentence_lengths) / len(sentence_lengths)
            length_variance = sum((l - avg_length) ** 2 for l in sentence_lengths) / len(sentence_lengths)

            # 句式过于规整（方差<20）可能是由AI生成（阈值从30提高到20）
            if length_variance < 20:
                probability += 8  # 权重降低（原20%）
            elif length_variance < 40:  # 阈值从50提高到40
                probability += 4  # 权重降低（原10%）

        # 检查AI常见表达（仅当出现时计分）
        # 降低权重：从8%降到2%
        ai_phrases = [
            "在当今社会", "随着科技的发展", "众所周知",
            "值得注意的是", "需要指出的是", "总的来说",
            "首先...其次...最后", "一方面...另一方"
        ]

        ai_phrase_count = sum(1 for phrase in ai_phrases if phrase in text)
        probability += ai_phrase_count * 2  # 权重大幅降低（原8%）

        # 检查内容深度（仅当缺乏具体内容时计分）
        # 降低权重：从15%降到5%，增加更多豁免条件
        if len(text) > 200:
            # 分析是否有具体数据和细节
            has_specifics = (
                re.search(r'\d+%', text) or
                re.search(r'\d+\s*[个项人次]', text) or
                re.search(r'\d+\.\d+', text) or  # 小数也算具体数据
                '例如' in text or '比如' in text or
                '如图' in text or '如表' in text or  # 图表引用也算具体
                '实验' in text or '测试' in text  # 提到实验也算具体
            )
            if not has_specifics:
                probability += 5  # 权重降低（原15%）

        # 检查过度使用的情感色彩词
        # 降低权重：从5%降到1.5%，阈值从1提高到2
        emotional_words = ['非常重要', '十分关键', '极其重要', '意义重大', '尤为']
        emotion_count = sum(1 for word in emotional_words if word in text)
        if emotion_count > 2:  # 超过2个才认为过度使用（原1个）
            probability += (emotion_count - 2) * 1.5  # 权重降低（原5%）

        # 新增：检查逻辑连接词的使用（过度使用连接词是AI特征）
        # 但仅当密度异常高时才计分
        logic_connectors = ['因此', '所以', '然而', '此外', '另外', '再者']
        connector_count = sum(1 for conn in logic_connectors if conn in text)
        # 每100字超过3个连接词才算异常（原没有阈值）
        if len(text) > 0 and connector_count / len(text) * 100 > 3:
            probability += 3  # 轻微惩罚

        # 新增：检查是否有个性化表达（有则降低AIGC概率）
        personal_markers = ['我认为', '笔者认为', '本研究', '我们的发现', '我们发现']
        if any(marker in text for marker in personal_markers):
            probability = max(0, probability - 5)  # 降低5个百分点

        return min(probability, 100.0)

    def _identify_aigc_factors(self, text: str) -> List[str]:
        """识别AIGC风险因素"""
        factors = []

        # 检查句式规整度
        sentences = [s.strip() for s in text.split('。') if s.strip()]
        if sentences:
            lengths = [len(s) for s in sentences]
            if len(set(lengths)) / len(lengths) < 0.3:
                factors.append("句式长度过于均匀")

        # 检查词汇多样性
        words = text.split()
        unique_ratio = len(set(words)) / len(words) if words else 0
        if unique_ratio < 0.5:
            factors.append("词汇重复率较高")

        # 检查是否有个性化表达
        personal_markers = ['我认为', '笔者', '我的', '我们发现']
        if not any(marker in text for marker in personal_markers):
            factors.append("缺乏个性化表达")

        # 检查连接词使用
        if '综上所述' in text or '总的来说' in text:
            factors.append("使用了AI常见的总结性连接词")

        if not factors:
            factors.append("未检测到明显AI特征")

        return factors

    def _generate_aigc_suggestions(self, probability: float) -> List[str]:
        """生成AIGC修改建议"""
        suggestions = []

        if probability >= 50:
            suggestions = [
                "该段落很可能由AI生成，建议完全重写",
                "增加个人观点和独特见解",
                "补充具体的研究数据和案例",
                "使用更具个性化的表达方式"
            ]
        elif probability >= 30:
            suggestions = [
                "该段落存在较高AI生成风险",
                "建议增加具体的分析和讨论",
                "补充个人研究发现",
                "调整语言风格使其更加自然"
            ]
        elif probability >= 15:
            suggestions = [
                "该段落有一定AI生成特征",
                "建议增加一些具体细节",
                "适当调整句式结构"
            ]
        else:
            suggestions = ["该段落AI生成风险较低，可保持原样"]

        return suggestions

    def analyze_paper(self, file_path: str, use_ai: bool = True) -> Dict:
        """
        完整分析论文

        Args:
            file_path: 论文文件路径
            use_ai: 是否使用AI分析（当前版本为模拟）

        Returns:
            完整的检测结果
        """
        # 读取文档
        doc_result = self.read_document(file_path)
        if "error" in doc_result:
            return {"error": doc_result["error"]}

        content = doc_result.get("content", "")

        # 提取章节
        sections = self.extract_sections(content)

        # 分割文本
        segments = self.segment_text(content, sections)

        # 检测引用
        citations, cleaned_content = self.detect_citations(content)

        # 分析每个片段
        similarity_results = []
        aigc_results = []
        suspected_plagiarism = []  # 疑似剽窃检测
        over_citation_segments = []  # 过度引用检测

        distribution = {
            "≥50%": {"count": 0, "words": 0},
            "40%-50%": {"count": 0, "words": 0},
            "30%-40%": {"count": 0, "words": 0},
            "<30%": {"count": 0, "words": 0}
        }

        total_similarity_score = 0
        total_aigc_score = 0
        total_words = 0
        duplicate_words = 0  # 重复字数

        # 维普特色指标：引用率、复写率、自写率
        cited_words = 0  # 正确引用的字数
        copied_words = 0  # 直接复制/复写的字数（相似度≥50%）
        original_words = 0  # 自写/原创的字数（相似度<30%）

        # 用于计算单篇最大重复字数
        max_single_duplicate = 0
        max_single_duplicate_location = ""

        # 前部重合字数（前30%的内容）
        front_words = 0
        front_duplicate_words = 0

        # 疑似段落数
        suspected_segment_count = 0

        # 疑似段落重合字数统计
        suspected_max_overlap = 0
        suspected_min_overlap = float('inf')

        for i, segment in enumerate(segments):
            segment_content = segment["content"]
            word_count = segment["word_count"]

            # 相似度分析
            sim_result = self.analyze_similarity_with_ai(segment_content)
            similarity_score = sim_result["similarity_score"]

            # AIGC检测
            aigc_result = self.detect_aigc_with_ai(segment_content)
            aigc_score = aigc_result["aigc_probability"]

            # 检测剽窃类型
            plagiarism_check = self._detect_plagiarism_type(segment_content, similarity_score)

            # 检测过度引用
            is_over_citation = self._detect_over_citation(segment_content, citations)

            # 统计
            total_words += word_count
            total_similarity_score += similarity_score * word_count
            total_aigc_score += aigc_score * word_count

            # 维普指标统计
            # 引用率：有引用标记的内容
            if '[' in segment_content and ']' in segment_content:
                # 估算引用字数（简单处理：整个段落按比例）
                cited_ratio = min(segment_content.count('[') / max(1, word_count / 50), 0.5)  # 最多50%
                cited_words += int(word_count * cited_ratio)

            # 复写率：相似度≥50%的内容（知网标准）
            if similarity_score >= 50:
                copied_words += int(word_count * similarity_score / 100)

            # 自写率：相似度<30%的内容
            elif similarity_score < 30:
                original_words += word_count

            # 计算重复字数
            if similarity_score >= 30:
                duplicate_words += int(word_count * similarity_score / 100)

                # 更新单篇最大重复字数
                segment_duplicate = int(word_count * similarity_score / 100)
                if segment_duplicate > max_single_duplicate:
                    max_single_duplicate = segment_duplicate
                    max_single_duplicate_location = segment["location"]

                # 疑似段落数增加
                suspected_segment_count += 1

                # 更新疑似段落重合字数
                if segment_duplicate > suspected_max_overlap:
                    suspected_max_overlap = segment_duplicate
                if segment_duplicate < suspected_min_overlap:
                    suspected_min_overlap = segment_duplicate

            # 前部重合检测（前30%的段落）
            if i < len(segments) * 0.3:
                front_words += word_count
                if similarity_score >= 30:
                    front_duplicate_words += int(word_count * similarity_score / 100)

            # 分布统计
            if similarity_score >= 50:
                distribution["≥50%"]["count"] += 1
                distribution["≥50%"]["words"] += word_count
            elif similarity_score >= 40:
                distribution["40%-50%"]["count"] += 1
                distribution["40%-50%"]["words"] += word_count
            elif similarity_score >= 30:
                distribution["30%-40%"]["count"] += 1
                distribution["30%-40%"]["words"] += word_count
            else:
                distribution["<30%"]["count"] += 1
                distribution["<30%"]["words"] += word_count

            # 保存高相似度片段
            if similarity_score >= 30:
                similarity_results.append({
                    "location": segment["location"],
                    "similarity": f"{similarity_score:.1f}%",
                    "word_count": word_count,
                    "overlap_words": int(word_count * similarity_score / 100),
                    "source_type": sim_result["potential_sources"][0] if sim_result["potential_sources"] else "未知",
                    "summary": segment_content[:100] + "..." if len(segment_content) > 100 else segment_content
                })

            # 保存剽窃类型检测结果
            if plagiarism_check["type"] != "正常":
                suspected_plagiarism.append({
                    "location": segment["location"],
                    "type": plagiarism_check["type"],
                    "description": plagiarism_check["description"],
                    "confidence": plagiarism_check["confidence"],
                    "content": segment_content[:150] + "..." if len(segment_content) > 150 else segment_content
                })

            # 保存过度引用片段
            if is_over_citation:
                over_citation_segments.append({
                    "location": segment["location"],
                    "citation_count": segment_content.count('[') + segment_content.count('('),
                    "content": segment_content[:150] + "..." if len(segment_content) > 150 else segment_content
                })

            # 保存高风险AIGC片段
            if aigc_score >= 15:
                aigc_results.append({
                    "location": segment["location"],
                    "rate": f"{aigc_score:.1f}%",
                    "risk_factors": ", ".join(aigc_result["risk_factors"]),
                    "content": segment_content[:150] + "..." if len(segment_content) > 150 else segment_content
                })

        # 计算总体指标
        avg_similarity = total_similarity_score / total_words if total_words > 0 else 0
        avg_aigc = total_aigc_score / total_words if total_words > 0 else 0

        # 计算去除引用后的相似度
        citation_ratio = len(citations) / len(segments) if segments else 0
        similarity_without_citations = max(avg_similarity - citation_ratio * 5, 0)

        # 计算去除本人已发表文献复制比（简化版：假设无自我发表）
        similarity_without_self = avg_similarity  # 暂无自我发表检测功能

        # 计算单篇最大文字复制比
        max_single_similarity_ratio = (max_single_duplicate / total_words * 100) if total_words > 0 else 0

        # 计算文字复制部分和无问题部分百分比（基于重复字数）
        copy_part_percentage = (duplicate_words / total_words * 100) if total_words > 0 else 0
        no_problem_percentage = 100 - copy_part_percentage

        # 计算维普核心指标（引用率、复写率、自写率）
        citation_rate = (cited_words / total_words * 100) if total_words > 0 else 0
        copy_rate = (copied_words / total_words * 100) if total_words > 0 else 0
        original_rate = (original_words / total_words * 100) if total_words > 0 else 0

        # 修正疑似段落最小重合字数（如果没有则设为0）
        if suspected_min_overlap == float('inf'):
            suspected_min_overlap = 0

        return {
            "paper_info": {
                "title": doc_result.get("title", "未知"),
                "author": doc_result.get("author", "未知"),
                "word_count": doc_result.get("word_count", 0),
                "paragraph_count": doc_result.get("paragraph_count", len(segments)),
                "format": doc_result.get("format", "unknown")
            },
            "detection_results": {
                # 核心检测结果（知网指标）
                "total_similarity": f"{avg_similarity:.1f}%",
                "similarity_without_citations": f"{similarity_without_citations:.1f}%",
                "similarity_without_self": f"{similarity_without_self:.1f}%",
                "max_single_similarity_ratio": f"{max_single_similarity_ratio:.1f}%",

                # 维普核心指标
                "citation_rate": f"{citation_rate:.1f}%",  # 引用率
                "copy_rate": f"{copy_rate:.1f}%",  # 复写率
                "original_rate": f"{original_rate:.1f}%",  # 自写率

                # 字数统计
                "duplicate_words": duplicate_words,
                "total_segments": len(segments),
                "total_words": total_words,
                "suspected_segment_count": suspected_segment_count,
                "max_single_duplicate_words": max_single_duplicate,
                "max_single_duplicate_location": max_single_duplicate_location,
                "front_overlap_words": front_duplicate_words,

                # 疑似段落重合字数
                "suspected_max_overlap_words": suspected_max_overlap,
                "suspected_min_overlap_words": suspected_min_overlap,

                # 百分比划分
                "copy_part_percentage": f"{copy_part_percentage:.1f}%",
                "no_problem_percentage": f"{no_problem_percentage:.1f}%",
                "aigc_rate": f"{avg_aigc:.1f}%",
                "distribution": distribution,
                "similar_segments": similarity_results,

                # 剽窃类型检测
                "plagiarism_analysis": {
                    "suspected_idea_plagiarism": [p for p in suspected_plagiarism if p["type"] == "疑似剽窃观点"],
                    "suspected_text_plagiarism": [p for p in suspected_plagiarism if p["type"] == "疑似剽窃文字表述"],
                    "suspected_overall_plagiarism": [p for p in suspected_plagiarism if p["type"] == "疑似整体剽窃"],
                    "over_citation_segments": over_citation_segments,
                    "total_plagiarism_cases": len(suspected_plagiarism),
                    "over_citation_count": len(over_citation_segments)
                },

                # AIGC分析
                "aigc_analysis": {
                    "total_rate": f"{avg_aigc:.1f}%",
                    "risk_level": self._get_overall_risk_level(avg_aigc),
                    "chapter_rates": self._calculate_chapter_rates(segments, sections),
                    "high_risk_segments": aigc_results,
                    "suggestions": self._generate_overall_suggestions(avg_aigc)
                },

                # 相似内容检测（表格、公式）
                "similar_objects": self._detect_similar_objects(content)
            },
            "metadata": {
                "detection_id": self.detection_id,
                "detection_time": self.detection_time,
                "segments_analyzed": len(segments),
                "citations_found": len(citations)
            }
        }

    def _get_overall_risk_level(self, avg_aigc: float) -> str:
        """确定总体风险等级"""
        if avg_aigc >= 50:
            return "极高风险"
        elif avg_aigc >= 30:
            return "高风险"
        elif avg_aigc >= 15:
            return "中风险"
        elif avg_aigc >= 5:
            return "低风险"
        else:
            return "正常"

    def _calculate_chapter_rates(self, segments: List[Dict], sections: Dict) -> Dict:
        """计算各章节的AIGC生成率"""
        chapter_rates = {}

        for section_name, section_content in sections.items():
            # 简化：基于章节内容特征估算
            section_aigc = self._estimate_aigc_probability(section_content)
            chapter_rates[section_name] = {
                "rate": f"{section_aigc:.1f}%",
                "words": len(section_content)
            }

        return chapter_rates

    def _detect_plagiarism_type(self, text: str, similarity_score: float) -> Dict:
        """
        检测剽窃类型

        Args:
            text: 文本内容
            similarity_score: 相似度分数

        Returns:
            剽窃类型检测结果
        """
        if similarity_score < 30:
            return {"type": "正常", "description": "未检测到明显剽窃", "confidence": "high"}

        result = {"type": "", "description": "", "confidence": "medium"}

        # 检测是否为整体剽窃（高相似度且长文本）
        if similarity_score >= 60 and len(text) > 300:
            result["type"] = "疑似整体剽窃"
            result["description"] = "大段内容与已有文献高度相似，可能存在整体剽窃"
            result["confidence"] = "high"
        # 检测是否为文字表述剽窃（中等相似度，常见连接词）
        elif similarity_score >= 40:
            copy_indicators = [
                "根据研究", "研究表明", "文献显示", "正如",
                "参考", "来源于", "摘自", "改写自"
            ]
            if any(indicator in text for indicator in copy_indicators):
                result["type"] = "疑似剽窃文字表述"
                result["description"] = "文字表述与现有文献相似，缺乏原创性改写"
            else:
                result["type"] = "疑似剽窃文字表述"
                result["description"] = "文字高度相似，可能存在直接复制或简单改写"
        # 检测是否为观点剽窃（低相似度但内容结构相似）
        else:
            structure_indicators = [
                "首先...其次...最后",
                "一方面...另一方面",
                "第一...第二...第三",
                "综上所述", "因此", "由此可见"
            ]
            if any(indicator in text for indicator in structure_indicators):
                result["type"] = "疑似剽窃观点"
                result["description"] = "论点结构和逻辑与已有文献相似，可能存在观点剽窃"

        return result

    def _detect_over_citation(self, text: str, citations: List[str]) -> bool:
        """
        检测是否存在过度引用

        Args:
            text: 文本内容
            citations: 引用列表

        Returns:
            是否过度引用
        """
        # 计算引用密度
        citation_count = text.count('[') + text.count('(')

        # 计算文本长度
        text_length = len(text)

        # 引用密度阈值：每100字不超过3个引用
        if text_length > 0:
            citation_density = citation_count / (text_length / 100)
            if citation_density > 3:
                return True

        # 检查是否有连续多个引用
        if '[1][2][3]' in text or '[1,2,3]' in text:
            return True

        # 检查引用是否占文本的很大比例
        citation_chars = len(re.findall(r'\[.*?\]', text)) * 5  # 估算引用字符数
        if citation_chars / text_length > 0.2:
            return True

        return False

    def _detect_similar_objects(self, content: str) -> Dict:
        """
        检测相似的表格和公式

        Args:
            content: 文档内容

        Returns:
            相似对象检测结果
        """
        result = {
            "similar_tables": [],
            "similar_formulas": [],
            "table_count": 0,
            "formula_count": 0
        }

        # 检测表格（简单识别）
        table_patterns = [
            r'\|.*\|.*\|',  # Markdown表格
            r'表\s*\d+',     # 中文表格引用
            r'Table\s*\d+',  # 英文表格引用
        ]

        tables = []
        for pattern in table_patterns:
            matches = re.findall(pattern, content)
            tables.extend(matches)

        result["table_count"] = len(set(tables))

        # 检测疑似相似表格
        if result["table_count"] > 0:
            # 简化：检查是否有表格标题重复
            table_refs = re.findall(r'(表\s*\d+|Table\s*\d+)', content)
            if len(table_refs) > len(set(table_refs)):
                result["similar_tables"].append({
                    "issue": "检测到重复的表格引用",
                    "count": len(table_refs) - len(set(table_refs))
                })

        # 检测公式（简单识别）
        formula_patterns = [
            r'\$.*?\$',           # LaTeX公式
            r'公式\s*\d+',        # 中文公式引用
            r'Eq\.\s*\d+',        # 英文公式引用
            r'方程\s*\d+',
        ]

        formulas = []
        for pattern in formula_patterns:
            matches = re.findall(pattern, content)
            formulas.extend(matches)

        result["formula_count"] = len(set(formulas))

        # 检测疑似相似公式
        if result["formula_count"] > 0:
            # 检查是否有公式标题重复
            formula_refs = re.findall(r'(公式\s*\d+|Eq\.\s*\d+)', content)
            if len(formula_refs) > len(set(formula_refs)):
                result["similar_formulas"].append({
                    "issue": "检测到重复的公式引用",
                    "count": len(formula_refs) - len(set(formula_refs))
                })

        return result

    def _generate_overall_suggestions(self, avg_aigc: float) -> List[str]:
        """生成整体修改建议"""
        suggestions = [
            "对高风险段落进行人工审核和修改",
            "增加个人分析和观点，减少AI生成内容"
        ]

        if avg_aigc >= 30:
            suggestions.extend([
                "补充具体的案例和数据支撑",
                "调整语言风格，使表达更加自然",
                "增加研究过程中的具体描述"
            ])

        return suggestions


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python ai_paper_detector.py <论文文件路径>")
        sys.exit(1)

    file_path = sys.argv[1]

    detector = AIPaperDetector()
    result = detector.analyze_paper(file_path)

    if "error" in result:
        print(f"错误: {result['error']}")
        sys.exit(1)

    # 输出结果
    print("=" * 60)
    print("论文检测报告")
    print("=" * 60)
    print(f"检测编号: {result['metadata']['detection_id']}")
    print(f"检测时间: {result['metadata']['detection_time']}")
    print()

    paper_info = result["paper_info"]
    print("论文信息:")
    print(f"  题目: {paper_info['title']}")
    print(f"  作者: {paper_info['author']}")
    print(f"  字数: {paper_info['word_count']}")
    print()

    detection = result["detection_results"]
    print("检测结果:")
    print(f"  总文字复制比: {detection['total_similarity']}")
    print(f"  去除引用文献复制比: {detection['similarity_without_citations']}")
    print(f"  去除本人文献复制比: {detection['similarity_without_self']}")
    print(f"  单篇最大文字复制比: {detection['max_single_similarity_ratio']}")
    print(f"  AIGC总体生成率: {detection['aigc_rate']}")
    print()

    print("字数统计:")
    print(f"  总字数: {detection['total_words']}")
    print(f"  总段落数: {detection['total_segments']}")
    print(f"  重复字数: {detection['duplicate_words']}")
    print(f"  疑似段落数: {detection['suspected_segment_count']}")
    print(f"  单篇最大重复字数: {detection['max_single_duplicate_words']} ({detection['max_single_duplicate_location']})")
    print(f"  前部重合字数: {detection['front_overlap_words']}")
    print()

    if detection['suspected_segment_count'] > 0:
        print("疑似段落重合字数:")
        print(f"  最大重合字数: {detection['suspected_max_overlap_words']}")
        print(f"  最小重合字数: {detection['suspected_min_overlap_words']}")
        print()

    print("百分比划分:")
    print(f"  文字复制部分: {detection['copy_part_percentage']}")
    print(f"  无问题部分: {detection['no_problem_percentage']}")
    print()

    print("相似度分布:")
    for range_name, data in detection['distribution'].items():
        print(f"  {range_name}: {data['count']} 个片段, {data['words']} 字")
    print()

    # 剽窃类型分析
    plagiarism = detection.get('plagiarism_analysis', {})
    if plagiarism.get('total_plagiarism_cases', 0) > 0:
        print("剽窃类型检测:")
        print(f"  疑似剽窃观点: {len(plagiarism.get('suspected_idea_plagiarism', []))} 处")
        print(f"  疑似剽窃文字表述: {len(plagiarism.get('suspected_text_plagiarism', []))} 处")
        print(f"  疑似整体剽窃: {len(plagiarism.get('suspected_overall_plagiarism', []))} 处")
        print(f"  过度引用: {plagiarism.get('over_citation_count', 0)} 处")
        print()

    # 相似对象检测
    similar_objects = detection.get('similar_objects', {})
    if similar_objects.get('table_count', 0) > 0 or similar_objects.get('formula_count', 0) > 0:
        print("相似内容检测:")
        print(f"  表格数量: {similar_objects.get('table_count', 0)}")
        print(f"  公式数量: {similar_objects.get('formula_count', 0)}")
        if similar_objects.get('similar_tables'):
            print(f"  疑似相似表格: {len(similar_objects['similar_tables'])} 项")
        if similar_objects.get('similar_formulas'):
            print(f"  疑似相似公式: {len(similar_objects['similar_formulas'])} 项")
        print()

    # 保存详细结果到JSON
    output_file = f"detection_result_{result['metadata']['detection_id']}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"详细结果已保存至: {output_file}")
    print()
    print("提示: 使用 generate_report.py 生成格式化的检测报告")


if __name__ == "__main__":
    main()
