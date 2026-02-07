#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Paper Detector - 论文检测（规则预处理 + Claude AI深度分析）

检测架构：
1. 规则检测（脚本）：快速预处理，提供基础数据
2. Claude AI深度分析（技能调用）：语义理解，以AI结果为准
"""

import sys
import re
import json
import random
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from enum import Enum


# ============================================================================
# 配置常量
# ============================================================================

MIN_SEGMENT_LENGTH = 100
MAX_SEGMENT_LENGTH = 2000
SIMILARITY_THRESHOLDS = {
    'high': 50,
    'medium': 40,
    'low': 30
}


# ============================================================================
# 枚举定义
# ============================================================================

class DetectionStep(Enum):
    """检测步骤枚举"""
    DOCUMENT_READING = "step1_document_reading"
    SECTION_EXTRACTION = "step2_section_extraction"
    TEXT_SEGMENTATION = "step3_text_segmentation"
    CITATION_DETECTION = "step4_citation_detection"
    SIMILARITY_DETECTION = "step5_similarity_detection"
    AIGC_DETECTION = "step6_aigc_detection"
    PLAGIARISM_TYPE_DETECTION = "step7_plagiarism_type_detection"
    OVER_CITATION_DETECTION = "step8_over_citation_detection"
    SIMILAR_OBJECTS_DETECTION = "step9_similar_objects_detection"
    ENHANCED_AI_DETECTION = "step10_enhanced_ai_detection"
    METRICS_CALCULATION = "step11_metrics_calculation"
    REPORT_GENERATION = "step12_report_generation"


# ============================================================================
# 核心检测类
# ============================================================================

class PaperDetector:
    """论文检测器 - 规则预处理（Claude AI深度分析由技能调用）"""

    def __init__(self):
        self.detection_id = self._generate_detection_id()
        self.detection_time = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
        self.ai_analysis_pending = True  # 标记需要Claude AI深度分析

    def _generate_detection_id(self) -> str:
        """生成检测编号"""
        now = datetime.now()
        return f"PD{now.strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"

    def read_document(self, file_path: str) -> Dict:
        """读取文档内容"""
        path = Path(file_path)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 改进字数统计
            content_for_count = content.replace(' ', '').replace('\n', '').replace('\r', '').replace('\t', '')
            word_count = len(content_for_count)

            return {
                "content": content,
                "word_count": word_count,
                "char_count": word_count,
                "title": "",
                "author": "",
                "paragraph_count": len([p for p in content.split('\n') if p.strip()])
            }
        except UnicodeDecodeError:
            try:
                with open(path, 'r') as f:
                    content = f.read()
                content_for_count = content.replace(' ', '').replace('\n', '').replace('\r', '').replace('\t', '')
                word_count = len(content_for_count)
                return {
                    "content": content,
                    "word_count": word_count,
                    "char_count": word_count,
                    "title": "",
                    "author": "",
                    "paragraph_count": len([p for p in content.split('\n') if p.strip()])
                }
            except Exception as e:
                return {"error": f"读取文件失败（编码错误）: {str(e)}"}
        except Exception as e:
            return {"error": f"读取文件失败: {str(e)}"}

    def extract_sections(self, content: str) -> Dict[str, str]:
        """从论文内容中提取主要章节"""
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

    def segment_text(self, content: str, sections: Dict = None) -> List[Dict]:
        """将文本分割成检测片段"""
        segments = []

        if sections:
            for section_name, section_content in sections.items():
                section_segments = self._split_section(section_content, section_name)
                segments.extend(section_segments)
        else:
            segments = self._split_section(content, "全文")

        return segments

    def _split_section(self, content: str, section_name: str) -> List[Dict]:
        """分割单个章节"""
        segments = []
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

    def detect_citations(self, content: str) -> Tuple[List[str], str]:
        """识别文本中的引用"""
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

    def _estimate_similarity(self, text: str) -> float:
        """估算文本相似度（从0%基准开始）"""
        score = 0.0

        # 检查过度使用常见学术短语
        common_phrases = [
            "综上所述", "因此", "然而", "此外", "另外",
            "研究表明", "根据", "可以看出", "由此可见",
            "一方面", "另一方面", "首先", "其次", "最后"
        ]

        phrase_count = sum(1 for phrase in common_phrases if phrase in text)
        if phrase_count > 8:
            score += (phrase_count - 8) * 0.5

        # 检查数字和统计数据的异常密度
        digit_ratio = sum(c.isdigit() for c in text) / len(text) if text else 0
        if digit_ratio > 0.15:
            score += 2

        # 检查引用标记
        citation_count = text.count('[')
        if citation_count > 0:
            score += citation_count * 0.3
        if len(text) > 0 and citation_count / len(text) * 100 > 8:
            score += 3

        # 检查专业术语密度
        technical_words = ['数据', '分析', '方法', '模型', '算法', '实验', '结果']
        tech_count = sum(1 for word in technical_words if word in text)
        if tech_count > 7:
            score += (tech_count - 7) * 0.5

        # 检查句式重复度
        sentences = [s.strip() for s in text.split('。') if s.strip()]
        if sentences:
            sentence_set = set(sentences)
            if len(sentence_set) < len(sentences) * 0.8:
                score += 1

        # 检查连续重复的词汇模式
        words = text.split()
        if len(words) > 10:
            for i in range(len(words) - 5):
                phrase = ' '.join(words[i:i+5])
                if text.count(phrase) > 2:
                    score += 0.5
                    break

        return min(score, 100.0)

    def _analyze_similarity_rules(self, segment: str) -> Dict:
        """分析文本片段的相似度"""
        return {
            "similarity_score": self._estimate_similarity(segment),
            "confidence": "medium",
            "potential_sources": self._identify_potential_sources(segment),
            "is_citation": self._check_if_citation(segment),
            "originality_score": self._calculate_originality(segment)
        }

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

    def _estimate_aigc_probability(self, text: str) -> float:
        """估算AIGC生成概率（从0%基准开始）"""
        probability = 0.0

        # 检查句式规整度
        sentences = [s.strip() for s in text.split('。') if s.strip()]
        if sentences:
            sentence_lengths = [len(s) for s in sentences]
            avg_length = sum(sentence_lengths) / len(sentence_lengths)
            length_variance = sum((l - avg_length) ** 2 for l in sentence_lengths) / len(sentence_lengths)

            if length_variance < 20:
                probability += 8
            elif length_variance < 40:
                probability += 4

        # 检查AI常见表达
        ai_phrases = [
            "在当今社会", "随着科技的发展", "众所周知",
            "值得注意的是", "需要指出的是", "总的来说",
            "首先...其次...最后", "一方面...另一方面"
        ]

        ai_phrase_count = sum(1 for phrase in ai_phrases if phrase in text)
        probability += ai_phrase_count * 2

        # 检查内容深度
        if len(text) > 200:
            has_specifics = (
                re.search(r'\d+%', text) or
                re.search(r'\d+\s*[个项人次]', text) or
                re.search(r'\d+\.\d+', text) or
                '例如' in text or '比如' in text or
                '如图' in text or '如表' in text or
                '实验' in text or '测试' in text
            )
            if not has_specifics:
                probability += 5

        # 检查过度使用的情感色彩词
        emotional_words = ['非常重要', '十分关键', '极其重要', '意义重大', '尤为']
        emotion_count = sum(1 for word in emotional_words if word in text)
        if emotion_count > 2:
            probability += (emotion_count - 2) * 1.5

        # 检查逻辑连接词的使用
        logic_connectors = ['因此', '所以', '然而', '此外', '另外', '再者']
        connector_count = sum(1 for conn in logic_connectors if conn in text)
        if len(text) > 0 and connector_count / len(text) * 100 > 3:
            probability += 3

        # 检查个性化表达
        personal_markers = ['我认为', '笔者认为', '本研究', '我们的发现', '我们发现']
        if any(marker in text for marker in personal_markers):
            probability = max(0, probability - 5)

        return min(probability, 100.0)

    def _detect_aigc_rules(self, segment: str) -> Dict:
        """检测AIGC内容"""
        probability = self._estimate_aigc_probability(segment)

        # 确定风险等级
        if probability >= 50:
            risk_level = "极高风险"
        elif probability >= 30:
            risk_level = "高风险"
        elif probability >= 15:
            risk_level = "中风险"
        elif probability >= 5:
            risk_level = "低风险"
        else:
            risk_level = "正常"

        # 识别风险因素
        risk_factors = self._identify_aigc_factors(segment)

        return {
            "aigc_probability": probability,
            "risk_level": risk_level,
            "risk_factors": risk_factors
        }

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

        # 检查个性化表达
        personal_markers = ['我认为', '笔者', '我的', '我们发现']
        if not any(marker in text for marker in personal_markers):
            factors.append("缺乏个性化表达")

        # 检查连接词使用
        if '综上所述' in text or '总的来说' in text:
            factors.append("使用了AI常见的总结性连接词")

        if not factors:
            factors.append("未检测到明显AI特征")

        return factors

    def _detect_plagiarism_type(self, text: str, similarity_score: float) -> Dict:
        """检测剽窃类型"""
        if similarity_score < 30:
            return {"type": "正常", "description": "未检测到明显剽窃", "confidence": "high"}

        result = {"type": "", "description": "", "confidence": "medium"}

        # 检测是否为整体剽窃
        if similarity_score >= 60 and len(text) > 300:
            result["type"] = "疑似整体剽窃"
            result["description"] = "大段内容与已有文献高度相似，可能存在整体剽窃"
            result["confidence"] = "high"
        # 检测是否为文字表述剽窃
        elif similarity_score >= 40:
            result["type"] = "疑似剽窃文字表述"
            result["description"] = "文字高度相似，可能存在直接复制或简单改写"
        # 检测是否为观点剽窃
        else:
            result["type"] = "疑似剽窃观点"
            result["description"] = "论点结构和逻辑与已有文献相似，可能存在观点剽窃"

        return result

    def _detect_over_citation(self, text: str, citations: List[str]) -> bool:
        """检测是否存在过度引用"""
        citation_count = text.count('[') + text.count('(')
        text_length = len(text)

        if text_length > 0:
            citation_density = citation_count / (text_length / 100)
            if citation_density > 3:
                return True

        if '[1][2][3]' in text or '[1,2,3]' in text:
            return True

        return False

    def _detect_similar_objects(self, content: str) -> Dict:
        """检测相似的表格和公式"""
        result = {
            "similar_tables": [],
            "similar_formulas": [],
            "table_count": 0,
            "formula_count": 0
        }

        # 检测表格
        table_patterns = [
            r'\|.*\|.*\|',
            r'表\s*\d+',
            r'Table\s*\d+',
        ]

        tables = []
        for pattern in table_patterns:
            matches = re.findall(pattern, content)
            tables.extend(matches)

        result["table_count"] = len(set(tables))

        # 检测公式
        formula_patterns = [
            r'\$.*?\$',
            r'公式\s*\d+',
            r'Eq\.\s*\d+',
        ]

        formulas = []
        for pattern in formula_patterns:
            matches = re.findall(pattern, content)
            formulas.extend(matches)

        result["formula_count"] = len(set(formulas))

        return result

    def analyze_paper(self, file_path: str) -> Dict:
        """完整分析论文"""
        print("  📖 读取文档...")
        doc_result = self.read_document(file_path)

        if "error" in doc_result:
            return {"error": doc_result["error"]}

        content = doc_result.get("content", "")

        print("  📑 提取章节...")
        sections = self.extract_sections(content)
        print(f"     识别到 {len(sections)} 个章节")

        print("  ✂️  分割文本...")
        segments = self.segment_text(content, sections)
        print(f"     分割为 {len(segments)} 个片段")

        print("  🔍 识别引用...")
        citations, cleaned_content = self.detect_citations(content)
        print(f"     识别到 {len(citations)} 个引用标记")

        # 初始化统计数据
        distribution = {
            "≥50%": {"count": 0, "words": 0},
            "40%-50%": {"count": 0, "words": 0},
            "30%-40%": {"count": 0, "words": 0},
            "<30%": {"count": 0, "words": 0}
        }

        total_words = 0
        total_similarity_score = 0
        total_aigc_score = 0
        duplicate_words = 0
        suspected_segment_count = 0
        max_single_duplicate = 0
        max_single_duplicate_location = ""

        similar_segments = []
        suspected_plagiarism = []
        over_citation_segments = []
        aigc_results = []

        # 维普指标
        cited_words = 0
        copied_words = 0
        original_words = 0

        print("  🔬 分析相似度（规则预处理）...")
        print("  🤖 检测AIGC（规则预处理）...")
        print("     ℹ️  Claude AI深度分析由技能自动调用")

        for i, segment in enumerate(segments):
            segment_content = segment["content"]
            word_count = segment["word_count"]

            # 规则检测：相似度分析
            sim_result = self._analyze_similarity_rules(segment_content)
            similarity_score = sim_result["similarity_score"]
            sim_result["ai_analyzed"] = False  # 标记为规则检测，等待Claude AI分析
            sim_result["needs_ai_analysis"] = True  # 标记需要Claude AI深度分析

            # 规则检测：AIGC检测
            aigc_result = self._detect_aigc_rules(segment_content)
            aigc_score = aigc_result["aigc_probability"]
            aigc_result["ai_analyzed"] = False  # 标记为规则检测，等待Claude AI分析
            aigc_result["needs_ai_analysis"] = True  # 标记需要Claude AI深度分析

            # 统计
            total_words += word_count
            total_similarity_score += similarity_score * word_count
            total_aigc_score += aigc_score * word_count

            # 维普指标统计
            if '[' in segment_content and ']' in segment_content:
                cited_ratio = min(segment_content.count('[') / max(1, word_count / 50), 0.5)
                cited_words += int(word_count * cited_ratio)

            if similarity_score >= 50:
                copied_words += int(word_count * similarity_score / 100)
            elif similarity_score < 30:
                original_words += word_count

            # 计算重复字数
            if similarity_score >= 30:
                segment_duplicate = int(word_count * similarity_score / 100)
                duplicate_words += segment_duplicate
                suspected_segment_count += 1

                # 更新单篇最大重复
                if segment_duplicate > max_single_duplicate:
                    max_single_duplicate = segment_duplicate
                    max_single_duplicate_location = segment["location"]

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
                similar_segments.append({
                    "location": segment["location"],
                    "similarity": f"{similarity_score:.1f}%",
                    "word_count": word_count,
                    "overlap_words": int(word_count * similarity_score / 100),
                    "source_type": sim_result["potential_sources"][0] if sim_result["potential_sources"] else "未知",
                    "summary": segment_content[:100] + "..." if len(segment_content) > 100 else segment_content
                })

            # 剽窃类型检测
            plagiarism_check = self._detect_plagiarism_type(segment_content, similarity_score)
            if plagiarism_check["type"] != "正常":
                suspected_plagiarism.append({
                    "location": segment["location"],
                    "type": plagiarism_check["type"],
                    "description": plagiarism_check["description"],
                    "confidence": plagiarism_check["confidence"],
                    "content": segment_content[:150] + "..." if len(segment_content) > 150 else segment_content
                })

            # 过度引用检测
            is_over_citation = self._detect_over_citation(segment_content, citations)
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

        # 去除引用后的相似度
        citation_ratio = len(citations) / len(segments) if segments else 0
        similarity_without_citations = max(avg_similarity - citation_ratio * 5, 0)
        similarity_without_self = avg_similarity

        # 单篇最大文字复制比
        max_single_similarity_ratio = (max_single_duplicate / total_words * 100) if total_words > 0 else 0

        # 百分比划分
        copy_part_percentage = (duplicate_words / total_words * 100) if total_words > 0 else 0
        no_problem_percentage = 100 - copy_part_percentage

        # 计算维普核心指标
        citation_rate = (cited_words / total_words * 100) if total_words > 0 else 0
        copy_rate = (copied_words / total_words * 100) if total_words > 0 else 0
        original_rate = (original_words / total_words * 100) if total_words > 0 else 0

        # 相似内容检测
        similar_objects = self._detect_similar_objects(content)

        # AIGC分析
        aigc_analysis = {
            "total_rate": f"{avg_aigc:.1f}%",
            "risk_level": self._get_overall_risk_level(avg_aigc),
            "high_risk_segments": aigc_results
        }

        print(f"     相似度检测完成: {len(similar_segments)} 个相似片段")
        print(f"     AIGC检测完成: {len(aigc_results)} 个高风险片段")

        return {
            "paper_info": doc_result,
            "detection_results": {
                # 知网核心指标
                "total_similarity": f"{avg_similarity:.1f}%",
                "similarity_without_citations": f"{similarity_without_citations:.1f}%",
                "similarity_without_self": f"{similarity_without_self:.1f}%",
                "max_single_similarity_ratio": f"{max_single_similarity_ratio:.1f}%",

                # 维普核心指标
                "citation_rate": f"{citation_rate:.1f}%",
                "copy_rate": f"{copy_rate:.1f}%",
                "original_rate": f"{original_rate:.1f}%",

                # 字数统计
                "total_words": total_words,
                "total_segments": len(segments),
                "duplicate_words": duplicate_words,
                "suspected_segment_count": suspected_segment_count,
                "max_single_duplicate_words": max_single_duplicate,
                "max_single_duplicate_location": max_single_duplicate_location,
                "front_overlap_words": 0,  # 简化版暂不计算

                # 百分比划分
                "copy_part_percentage": f"{copy_part_percentage:.1f}%",
                "no_problem_percentage": f"{no_problem_percentage:.1f}%",

                # 其他
                "aigc_rate": f"{avg_aigc:.1f}%",
                "distribution": distribution,
                "similar_segments": similar_segments,
                "plagiarism_analysis": {
                    "suspected_idea_plagiarism": [p for p in suspected_plagiarism if p["type"] == "疑似剽窃观点"],
                    "suspected_text_plagiarism": [p for p in suspected_plagiarism if p["type"] == "疑似剽窃文字表述"],
                    "suspected_overall_plagiarism": [p for p in suspected_plagiarism if p["type"] == "疑似整体剽窃"],
                    "over_citation_segments": over_citation_segments,
                    "total_plagiarism_cases": len(suspected_plagiarism),
                    "over_citation_count": len(over_citation_segments)
                },
                "similar_objects": similar_objects,
                "aigc_analysis": aigc_analysis
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

# ============================================================================
# 报告生成类
# ============================================================================

class ReportGenerator:
    """报告生成器"""

    def __init__(self, paper_info: Dict, detection_results: Dict):
        self.paper_info = paper_info
        self.detection_results = detection_results
        self.detection_id = self._generate_id()
        self.detection_time = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")

    def _generate_id(self) -> str:
        """生成检测编号"""
        now = datetime.now()
        return f"PD{now.strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"

    def generate_report(self) -> str:
        """生成统一检测报告"""
        lines = []
        lines.append("# 论文检测报告")
        lines.append("")

        # ========== 基本信息 ==========
        lines.append("## 一、基本信息")
        lines.append(f"- 论文题目：《{self.paper_info.get('title', '未知')}》")
        lines.append(f"- 作者：{self.paper_info.get('author', '未知')}")
        lines.append(f"- 检测时间：{self.detection_time}")
        lines.append(f"- 检测编号：{self.detection_id}")
        lines.append(f"- 原文总字数：{self.paper_info.get('word_count', 0)}字")
        lines.append("")

        # ========== 检测结果汇总 ==========
        lines.append("## 二、检测结果汇总")
        lines.append("")

        # 知网核心指标
        lines.append("**知网指标**")
        lines.append(f"- 总文字复制比：{self.detection_results.get('total_similarity', 'N/A')}")
        lines.append(f"- 去除引用文献复制比：{self.detection_results.get('similarity_without_citations', 'N/A')}")
        lines.append(f"- 去除本人已发表文献复制比：{self.detection_results.get('similarity_without_self', 'N/A')}")
        lines.append(f"- 单篇最大文字复制比：{self.detection_results.get('max_single_similarity_ratio', 'N/A')}")
        lines.append("")

        # 维普核心指标
        if 'citation_rate' in self.detection_results:
            lines.append("**维普指标**")
            lines.append(f"- 引用率：{self.detection_results.get('citation_rate', 'N/A')}")
            lines.append(f"- 复写率：{self.detection_results.get('copy_rate', 'N/A')}")
            lines.append(f"- 自写率：{self.detection_results.get('original_rate', 'N/A')}")
            lines.append("")

        # AIGC指标
        if 'aigc_rate' in self.detection_results:
            lines.append("**AIGC指标**")
            lines.append(f"- AIGC总体生成率：{self.detection_results.get('aigc_rate', 'N/A')}")
            lines.append("")

        # 百分比划分
        if 'copy_part_percentage' in self.detection_results:
            lines.append("**文字复制占比**")
            lines.append(f"- 文字复制部分：{self.detection_results.get('copy_part_percentage', 'N/A')}")
            lines.append(f"- 无问题部分：{self.detection_results.get('no_problem_percentage', 'N/A')}")
            lines.append("")

        # ========== 字数统计 ==========
        if 'duplicate_words' in self.detection_results:
            lines.append("## 三、字数统计")
            lines.append(f"- 总字数：{self.detection_results.get('total_words', 'N/A')}")
            lines.append(f"- 总段落数：{self.detection_results.get('total_segments', 'N/A')}")
            lines.append(f"- 重复字数：{self.detection_results.get('duplicate_words', 'N/A')}")
            lines.append(f"- 疑似段落数：{self.detection_results.get('suspected_segment_count', 'N/A')}")
            if 'max_single_duplicate_words' in self.detection_results:
                lines.append(f"- 单篇最大重复字数：{self.detection_results.get('max_single_duplicate_words', 'N/A')}")
                lines.append(f"- 单篇最大重复位置：{self.detection_results.get('max_single_duplicate_location', 'N/A')}")
            lines.append("")

        # ========== 相似度分布 ==========
        lines.append("## 四、相似度分布")
        lines.append("| 相似度区间 | 段落数 | 字数 |")
        lines.append("|-----------|--------|------|")

        distribution = self.detection_results.get('distribution', {})
        for range_name in ['≥50%', '40%-50%', '30%-40%', '<30%']:
            data = distribution.get(range_name, {'count': 0, 'words': 0})
            lines.append(f"| {range_name} | {data['count']} | {data['words']} |")

        lines.append("")

        # ========== 剽窃类型检测 ==========
        if 'plagiarism_analysis' in self.detection_results:
            plagiarism = self.detection_results['plagiarism_analysis']
            lines.append("## 五、剽窃类型检测")
            lines.append(f"- 疑似剽窃观点：{len(plagiarism.get('suspected_idea_plagiarism', []))} 处")
            lines.append(f"- 疑似剽窃文字表述：{len(plagiarism.get('suspected_text_plagiarism', []))} 处")
            lines.append(f"- 疑似整体剽窃：{len(plagiarism.get('suspected_overall_plagiarism', []))} 处")
            lines.append(f"- 过度引用：{plagiarism.get('over_citation_count', 0)} 处")
            lines.append("")

            # 详细列表
            if plagiarism.get('suspected_idea_plagiarism'):
                lines.append("### 疑似剽窃观点详情")
                for idx, item in enumerate(plagiarism['suspected_idea_plagiarism'][:10], 1):
                    lines.append(f"{idx}. **位置**：{item.get('location', 'N/A')}")
                    lines.append(f"   - 相似度：{item.get('similarity', 'N/A')}")
                    lines.append(f"   - 描述：{item.get('description', 'N/A')}")
                lines.append("")

            if plagiarism.get('suspected_text_plagiarism'):
                lines.append("### 疑似剽窃文字表述详情")
                for idx, item in enumerate(plagiarism['suspected_text_plagiarism'][:10], 1):
                    lines.append(f"{idx}. **位置**：{item.get('location', 'N/A')}")
                    lines.append(f"   - 相似度：{item.get('similarity', 'N/A')}")
                    lines.append(f"   - 字数：{item.get('word_count', 'N/A')}")
                lines.append("")

            if plagiarism.get('suspected_overall_plagiarism'):
                lines.append("### 疑似整体剽窃详情")
                for idx, item in enumerate(plagiarism['suspected_overall_plagiarism'][:10], 1):
                    lines.append(f"{idx}. **位置**：{item.get('location', 'N/A')}")
                    lines.append(f"   - 相似度：{item.get('similarity', 'N/A')}")
                    lines.append(f"   - 字数：{item.get('word_count', 'N/A')}")
                lines.append("")

        # ========== 相似片段详情 ==========
        if 'similar_segments' in self.detection_results and self.detection_results['similar_segments']:
            lines.append("## 六、相似片段详情")
            for idx, segment in enumerate(self.detection_results['similar_segments'][:20], 1):
                lines.append(f"### 片段 {idx}")
                lines.append(f"- **位置**：{segment.get('location', 'N/A')}")
                lines.append(f"- **相似度**：{segment.get('similarity', 'N/A')}")
                lines.append(f"- **字数**：{segment.get('word_count', 'N/A')}")
                lines.append(f"- **来源类型**：{segment.get('source_type', 'N/A')}")
                lines.append("")

        # ========== AIGC检测详细分析 ==========
        if 'aigc_analysis' in self.detection_results:
            aigc = self.detection_results['aigc_analysis']
            lines.append("## 七、AIGC检测分析")
            lines.append(f"- 总体生成率：{aigc.get('total_rate', 'N/A')}")
            lines.append(f"- 风险等级：{aigc.get('risk_level', 'N/A')}")
            lines.append("")

            # 各章节生成率
            if 'chapter_rates' in aigc:
                lines.append("### 各章节AIGC生成率")
                lines.append("| 章节 | 生成率 | 字数 |")
                lines.append("|------|--------|------|")
                for chapter, data in aigc['chapter_rates'].items():
                    lines.append(f"| {chapter} | {data.get('rate', 'N/A')} | {data.get('words', 'N/A')} |")
                lines.append("")

            # 高风险段落
            if aigc.get('high_risk_segments'):
                lines.append("### 高风险段落详情")
                for idx, segment in enumerate(aigc['high_risk_segments'][:10], 1):
                    lines.append(f"{idx}. **位置**：{segment.get('location', 'N/A')}")
                    lines.append(f"   - 生成率：{segment.get('rate', 'N/A')}")
                    lines.append(f"   - 风险因素：{segment.get('risk_factors', 'N/A')}")
                lines.append("")

        # ========== 相似内容检测 ==========
        if 'similar_objects' in self.detection_results:
            objects = self.detection_results['similar_objects']
            lines.append("## 八、相似内容检测")

            if objects.get('similar_tables'):
                lines.append(f"- 疑似相似表格：{len(objects['similar_tables'])} 个")
            if objects.get('similar_formulas'):
                lines.append(f"- 疑似相似公式：{len(objects['similar_formulas'])} 个")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("*本报告基于规则检测生成，Claude AI深度分析将由技能调用后覆盖结果。*")

        return "\n".join(lines)

    def save_report(self, report_text: str, output_path: str):
        """保存报告到文件"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report_text)
            print(f"     ✅ 报告已保存: {output_path}")
        except Exception as e:
            print(f"     ❌ 保存失败: {str(e)}")


# ============================================================================
# 主函数
# ============================================================================

def main():
    """主函数"""
    print("=" * 70)
    print("📚 论文检测 - 规则预处理 + Claude AI深度分析")
    print("=" * 70)
    print()

    # 检查参数
    if len(sys.argv) < 2:
        print("❌ 错误: 缺少论文文件路径")
        print()
        print("用法: python3 scripts/one_click_detect_standalone.py <论文文件>")
        print()
        print("示例:")
        print("  python3 /skills/paper-detector/scripts/one_click_detect_standalone.py paper.md")
        print("  python3 /skills/paper-detector/scripts/one_click_detect_standalone.py pager.md")
        sys.exit(1)

    paper_file = sys.argv[1]

    # 尝试读取文件，自动处理路径
    try:
        with open(paper_file, 'r', encoding='utf-8') as f:
            test = f.read()
    except FileNotFoundError:
        print(f"❌ 错误: 文件不存在: {paper_file}")
        sys.exit(1)

    print(f"📄 论文文件: {paper_file}")
    print()
    print("检测模式：")
    print("  • 规则检测（脚本）：快速预处理，提供基础数据")
    print("  • Claude AI深度分析（技能）：语义理解，以AI结果为准")
    print()

    try:
        # ==================== 步骤1: 执行检测 ====================
        print("=" * 70)
        print("步骤 1/2: 执行论文检测")
        print("=" * 70)
        print()

        detector = PaperDetector()
        result = detector.analyze_paper(paper_file)

        if "error" in result:
            print(f"❌ 检测失败: {result['error']}")
            sys.exit(1)

        print()
        print("✅ 检测完成!")
        print()

        # 显示关键结果
        detection_results = result.get("detection_results", {})
        print("📊 检测结果摘要:")
        print(f"  - 总字数: {detection_results.get('total_words', 'N/A')}")
        print(f"  - 总文字复制比: {detection_results.get('total_similarity', 'N/A')}")
        print(f"  - 去除引用文献复制比: {detection_results.get('similarity_without_citations', 'N/A')}")
        print(f"  - 单篇最大文字复制比: {detection_results.get('max_single_similarity_ratio', 'N/A')}")
        print(f"  - AIGC总体生成率: {detection_results.get('aigc_rate', 'N/A')}")
        print(f"  - 引用率: {detection_results.get('citation_rate', 'N/A')}")
        print(f"  - 复写率: {detection_results.get('copy_rate', 'N/A')}")
        print(f"  - 自写率: {detection_results.get('original_rate', 'N/A')}")
        print()

        # ==================== 保存检测结果 ====================
        detection_id = result.get("metadata", {}).get("detection_id", detector.detection_id)
        json_file = f"detection_result_{detection_id}.json"

        print(f"💾 保存检测结果: {json_file}")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print()

        # ==================== 步骤2: 生成报告 ====================
        print("=" * 70)
        print("步骤 2/2: 生成检测报告")
        print("=" * 70)
        print()

        report_gen = ReportGenerator(
            result.get("paper_info", {}),
            detection_results
        )

        base_name = Path(paper_file).stem

        # 生成检测报告
        print("📋 生成检测报告...")
        print()

        report = report_gen.generate_report()
        report_file = "reports" / f"{base_name}_检测报告.md"
        report_gen.save_report(report, str(report_file))

        print()
        print("=" * 70)
        print("🎉 检测和报告生成完成!")
        print("=" * 70)
        print()

        print("📁 输出文件:")
        print(f"  1. 检测结果: {json_file}")
        print(f"  2. 检测报告: {report_file}")
        print()

    except Exception as e:
        print(f"❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
