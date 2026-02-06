#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Paper Detector - 检测流程编排器

本模块定义了论文检测的强制流程，确保所有检测步骤按顺序执行，
所有检测项都被覆盖，并输出规范的检测报告。

⚠️ 重要说明：
1. 本流程是强制执行的，不能跳过任何步骤
2. 每个检测步骤都有明确的输入和输出
3. 所有步骤完成后才能生成检测报告
4. 检测报告必须包含所有检测项的结果
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from enum import Enum


class DetectionStep(Enum):
    """检测步骤枚举 - 定义所有必须执行的检测步骤"""

    # 步骤1: 文档读取与预处理
    DOCUMENT_READING = "step1_document_reading"

    # 步骤2: 章节提取
    SECTION_EXTRACTION = "step2_section_extraction"

    # 步骤3: 文本分割
    TEXT_SEGMENTATION = "step3_text_segmentation"

    # 步骤4: 引用识别
    CITATION_DETECTION = "step4_citation_detection"

    # 步骤5: 相似度检测（核心）
    SIMILARITY_DETECTION = "step5_similarity_detection"

    # 步骤6: AIGC检测（核心）
    AIGC_DETECTION = "step6_aigc_detection"

    # 步骤7: 剽窃类型检测（4种）
    PLAGIARISM_TYPE_DETECTION = "step7_plagiarism_type_detection"

    # 步骤8: 过度引用检测
    OVER_CITATION_DETECTION = "step8_over_citation_detection"

    # 步骤9: 相似内容检测（表格、公式）
    SIMILAR_OBJECTS_DETECTION = "step9_similar_objects_detection"

    # 步骤10: 增强AI检测（3项）
    ENHANCED_AI_DETECTION = "step10_enhanced_ai_detection"

    # 步骤11: 统计指标计算
    METRICS_CALCULATION = "step11_metrics_calculation"

    # 步骤12: 报告生成
    REPORT_GENERATION = "step12_report_generation"


class StepResult:
    """步骤结果类"""

    def __init__(self, step: DetectionStep, success: bool, data: Dict = None, error: str = None):
        self.step = step
        self.success = success
        self.data = data or {}
        self.error = error
        self.timestamp = datetime.now()

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "step": self.step.value,
            "step_name": self.step.name,
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        }


class DetectionWorkflow:
    """
    论文检测流程编排器

    强制执行所有检测步骤，确保完整性。
    """

    # 定义所有必须执行的检测步骤（按顺序）
    REQUIRED_STEPS = [
        DetectionStep.DOCUMENT_READING,
        DetectionStep.SECTION_EXTRACTION,
        DetectionStep.TEXT_SEGMENTATION,
        DetectionStep.CITATION_DETECTION,
        DetectionStep.SIMILARITY_DETECTION,
        DetectionStep.AIGC_DETECTION,
        DetectionStep.PLAGIARISM_TYPE_DETECTION,
        DetectionStep.OVER_CITATION_DETECTION,
        DetectionStep.SIMILAR_OBJECTS_DETECTION,
        DetectionStep.ENHANCED_AI_DETECTION,
        DetectionStep.METRICS_CALCULATION,
        DetectionStep.REPORT_GENERATION,
    ]

    def __init__(self, detector):
        """
        初始化检测流程

        Args:
            detector: AIPaperDetector实例
        """
        self.detector = detector
        self.results: List[StepResult] = []
        self.workflow_data = {}  # 存储步骤间的数据传递

    def execute_workflow(self, file_path: str, enhanced_ai_check: bool = True) -> Dict:
        """
        执行完整的检测流程（强制所有步骤）

        Args:
            file_path: 论文文件路径
            enhanced_ai_check: 是否执行增强AI检测（默认True）

        Returns:
            完整的检测结果和流程信息

        Raises:
            WorkflowError: 如果任何步骤失败
        """
        print("=" * 70)
        print("🔍 论文检测流程启动")
        print("=" * 70)
        print(f"⚠️  强制模式：将执行所有 {len(self.REQUIRED_STEPS)} 个检测步骤")
        print(f"📁 文件路径: {file_path}")
        print(f"🤖 增强AI检测: {'开启' if enhanced_ai_check else '关闭'}")
        print()

        # 清空之前的结果
        self.results = []
        self.workflow_data = {}

        # 逐步执行所有检测步骤
        for step in self.REQUIRED_STEPS:
            # 步骤10是可选的（增强AI检测）
            if step == DetectionStep.ENHANCED_AI_DETECTION and not enhanced_ai_check:
                print(f"⏭️  跳过步骤 {step.name}（未启用）")
                continue

            result = self._execute_step(step, file_path)
            self.results.append(result)

            if not result.success:
                raise WorkflowError(
                    f"检测步骤 '{step.name}' 失败: {result.error}",
                    step,
                    result
                )

            # 更新工作流数据
            self.workflow_data.update(result.data)

        print()
        print("=" * 70)
        print("✅ 检测流程全部完成")
        print("=" * 70)

        # 返回完整的检测结果和流程信息
        return {
            "detection_result": self.workflow_data,
            "workflow_info": self._get_workflow_summary()
        }

    def _execute_step(self, step: DetectionStep, file_path: str) -> StepResult:
        """
        执行单个检测步骤

        Args:
            step: 检测步骤
            file_path: 文件路径

        Returns:
            步骤执行结果
        """
        step_num = self.REQUIRED_STEPS.index(step) + 1
        total_steps = len(self.REQUIRED_STEPS)

        print(f"📍 步骤 {step_num}/{total_steps}: {self._get_step_description(step)}")
        print("-" * 70)

        try:
            if step == DetectionStep.DOCUMENT_READING:
                return self._step1_document_reading(file_path)

            elif step == DetectionStep.SECTION_EXTRACTION:
                return self._step2_section_extraction()

            elif step == DetectionStep.TEXT_SEGMENTATION:
                return self._step3_text_segmentation()

            elif step == DetectionStep.CITATION_DETECTION:
                return self._step4_citation_detection()

            elif step == DetectionStep.SIMILARITY_DETECTION:
                return self._step5_similarity_detection()

            elif step == DetectionStep.AIGC_DETECTION:
                return self._step6_aigc_detection()

            elif step == DetectionStep.PLAGIARISM_TYPE_DETECTION:
                return self._step7_plagiarism_type_detection()

            elif step == DetectionStep.OVER_CITATION_DETECTION:
                return self._step8_over_citation_detection()

            elif step == DetectionStep.SIMILAR_OBJECTS_DETECTION:
                return self._step9_similar_objects_detection()

            elif step == DetectionStep.ENHANCED_AI_DETECTION:
                return self._step10_enhanced_ai_detection()

            elif step == DetectionStep.METRICS_CALCULATION:
                return self._step11_metrics_calculation()

            elif step == DetectionStep.REPORT_GENERATION:
                return self._step12_report_generation()

            else:
                return StepResult(step, False, error=f"未知步骤: {step.name}")

        except Exception as e:
            print(f"❌ 执行失败: {str(e)}")
            return StepResult(step, False, error=str(e))

    def _get_step_description(self, step: DetectionStep) -> str:
        """获取步骤描述"""
        descriptions = {
            DetectionStep.DOCUMENT_READING: "文档读取与预处理",
            DetectionStep.SECTION_EXTRACTION: "章节提取",
            DetectionStep.TEXT_SEGMENTATION: "文本分割",
            DetectionStep.CITATION_DETECTION: "引用识别",
            DetectionStep.SIMILARITY_DETECTION: "相似度检测",
            DetectionStep.AIGC_DETECTION: "AIGC检测",
            DetectionStep.PLAGIARISM_TYPE_DETECTION: "剽窃类型检测（4种）",
            DetectionStep.OVER_CITATION_DETECTION: "过度引用检测",
            DetectionStep.SIMILAR_OBJECTS_DETECTION: "相似内容检测（表格、公式）",
            DetectionStep.ENHANCED_AI_DETECTION: "增强AI检测（3项）",
            DetectionStep.METRICS_CALCULATION: "统计指标计算",
            DetectionStep.REPORT_GENERATION: "报告生成",
        }
        return descriptions.get(step, step.name)

    # ========================================================================
    # 步骤1: 文档读取与预处理
    # ========================================================================

    def _step1_document_reading(self, file_path: str) -> StepResult:
        """
        步骤1: 读取文档并提取基本信息

        输出:
            - content: 文档内容
            - paper_info: 论文基本信息（标题、作者、字数等）
        """
        print("  📖 读取文档内容...")

        doc_result = self.detector.read_document(file_path)

        if "error" in doc_result:
            return StepResult(
                DetectionStep.DOCUMENT_READING,
                False,
                error=doc_result["error"]
            )

        print(f"  ✅ 成功读取文档")
        print(f"     - 字数: {doc_result.get('word_count', 0)}")
        print(f"     - 段落数: {doc_result.get('paragraph_count', 0)}")

        return StepResult(
            DetectionStep.DOCUMENT_READING,
            True,
            {
                "content": doc_result.get("content", ""),
                "paper_info": doc_result
            }
        )

    # ========================================================================
    # 步骤2: 章节提取
    # ========================================================================

    def _step2_section_extraction(self) -> StepResult:
        """
        步骤2: 提取论文章节结构

        输入: content
        输出:
            - sections: 章节字典
        """
        print("  📑 提取章节结构...")

        content = self.workflow_data.get("content", "")
        sections = self.detector.extract_sections(content)

        print(f"  ✅ 识别到 {len(sections)} 个章节:")
        for section_name in sections.keys():
            print(f"     - {section_name}")

        return StepResult(
            DetectionStep.SECTION_EXTRACTION,
            True,
            {"sections": sections}
        )

    # ========================================================================
    # 步骤3: 文本分割
    # ========================================================================

    def _step3_text_segmentation(self) -> StepResult:
        """
        步骤3: 将文本分割成检测片段

        输入: content, sections
        输出:
            - segments: 片段列表
        """
        print("  ✂️  分割文本片段...")

        content = self.workflow_data.get("content", "")
        sections = self.workflow_data.get("sections", {})

        segments = self.detector.segment_text(content, sections)

        print(f"  ✅ 成功分割为 {len(segments)} 个片段")
        print(f"     - 片段长度范围: {MIN_SEGMENT_LENGTH}-{MAX_SEGMENT_LENGTH}字")

        return StepResult(
            DetectionStep.TEXT_SEGMENTATION,
            True,
            {"segments": segments}
        )

    # ========================================================================
    # 步骤4: 引用识别
    # ========================================================================

    def _step4_citation_detection(self) -> StepResult:
        """
        步骤4: 识别文献引用

        输入: content
        输出:
            - citations: 引用列表
            - cleaned_content: 去除引用后的内容
        """
        print("  🔍 识别文献引用...")

        content = self.workflow_data.get("content", "")
        citations, cleaned_content = self.detector.detect_citations(content)

        print(f"  ✅ 识别到 {len(citations)} 个引用标记")
        print(f"     - 引用格式: [数字], (作者, 年份)")

        return StepResult(
            DetectionStep.CITATION_DETECTION,
            True,
            {
                "citations": citations,
                "cleaned_content": cleaned_content
            }
        )

    # ========================================================================
    # 步骤5: 相似度检测（核心）
    # ========================================================================

    def _step5_similarity_detection(self) -> StepResult:
        """
        步骤5: 对每个片段进行相似度分析

        输入: segments
        输出:
            - similarity_results: 相似度结果列表
            - distribution: 相似度分布统计
        """
        print("  🔬 相似度检测...")

        segments = self.workflow_data.get("segments", [])
        similarity_results = []
        distribution = {
            "≥50%": {"count": 0, "words": 0},
            "40%-50%": {"count": 0, "words": 0},
            "30%-40%": {"count": 0, "words": 0},
            "<30%": {"count": 0, "words": 0}
        }

        for segment in segments:
            segment_content = segment["content"]
            word_count = segment["word_count"]

            # 相似度分析
            sim_result = self.detector.analyze_similarity_with_ai(segment_content)
            similarity_score = sim_result["similarity_score"]

            # 统计分布
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

            # 保存结果
            similarity_results.append({
                "segment": segment,
                "similarity_score": similarity_score,
                "analysis": sim_result
            })

        print(f"  ✅ 完成 {len(segments)} 个片段的相似度分析")
        print(f"     - 高相似度(≥50%): {distribution['≥50%']['count']} 个")
        print(f"     - 中等相似度(40-50%): {distribution['40%-50%']['count']} 个")
        print(f"     - 低相似度(30-40%): {distribution['30%-40%']['count']} 个")
        print(f"     - 正常(<30%): {distribution['<30%']['count']} 个")

        return StepResult(
            DetectionStep.SIMILARITY_DETECTION,
            True,
            {
                "similarity_results": similarity_results,
                "distribution": distribution
            }
        )

    # ========================================================================
    # 步骤6: AIGC检测（核心）
    # ========================================================================

    def _step6_aigc_detection(self) -> StepResult:
        """
        步骤6: 对每个片段进行AIGC检测

        输入: segments
        输出:
            - aigc_results: AIGC检测结果列表
        """
        print("  🤖 AIGC检测...")

        segments = self.workflow_data.get("segments", [])
        aigc_results = []
        high_risk_count = 0

        for segment in segments:
            segment_content = segment["content"]

            # AIGC检测
            aigc_result = self.detector.detect_aigc_with_ai(segment_content)
            aigc_score = aigc_result["aigc_probability"]

            if aigc_score >= 15:
                high_risk_count += 1

            # 保存结果
            aigc_results.append({
                "segment": segment,
                "aigc_score": aigc_score,
                "detection": aigc_result
            })

        print(f"  ✅ 完成 {len(segments)} 个片段的AIGC检测")
        print(f"     - 高风险片段: {high_risk_count} 个")

        return StepResult(
            DetectionStep.AIGC_DETECTION,
            True,
            {"aigc_results": aigc_results}
        )

    # ========================================================================
    # 步骤7: 剽窃类型检测（4种）
    # ========================================================================

    def _step7_plagiarism_type_detection(self) -> StepResult:
        """
        步骤7: 检测4种剽窃类型

        检测项:
            1. 疑似剽窃观点
            2. 疑似剽窃文字表述
            3. 疑似整体剽窃
            4. 疑似整体剽窃

        输入: similarity_results
        输出:
            - plagiarism_analysis: 剽窃类型分析结果
        """
        print("  🎯 剽窃类型检测（4种类型）...")

        similarity_results = self.workflow_data.get("similarity_results", [])

        suspected_idea_plagiarism = []  # 疑似剽窃观点
        suspected_text_plagiarism = []  # 疑似剽窃文字表述
        suspected_overall_plagiarism = []  # 疑似整体剽窃

        for result in similarity_results:
            segment = result["segment"]
            similarity_score = result["similarity_score"]
            segment_content = segment["content"]

            # 检测剽窃类型
            plagiarism_check = self.detector._detect_plagiarism_type(
                segment_content, similarity_score
            )

            if plagiarism_check["type"] == "疑似剽窃观点":
                suspected_idea_plagiarism.append({
                    "location": segment["location"],
                    "type": plagiarism_check["type"],
                    "description": plagiarism_check["description"],
                    "confidence": plagiarism_check["confidence"],
                    "content": segment_content[:150] + "..." if len(segment_content) > 150 else segment_content
                })

            elif plagiarism_check["type"] == "疑似剽窃文字表述":
                suspected_text_plagiarism.append({
                    "location": segment["location"],
                    "type": plagiarism_check["type"],
                    "description": plagiarism_check["description"],
                    "confidence": plagiarism_check["confidence"],
                    "content": segment_content[:150] + "..." if len(segment_content) > 150 else segment_content
                })

            elif plagiarism_check["type"] == "疑似整体剽窃":
                suspected_overall_plagiarism.append({
                    "location": segment["location"],
                    "type": plagiarism_check["type"],
                    "description": plagiarism_check["description"],
                    "confidence": plagiarism_check["confidence"],
                    "content": segment_content[:150] + "..." if len(segment_content) > 150 else segment_content
                })

        print(f"  ✅ 完成4种剽窃类型检测:")
        print(f"     - 疑似剽窃观点: {len(suspected_idea_plagiarism)} 处")
        print(f"     - 疑似剽窃文字表述: {len(suspected_text_plagiarism)} 处")
        print(f"     - 疑似整体剽窃: {len(suspected_overall_plagiarism)} 处")

        return StepResult(
            DetectionStep.PLAGIARISM_TYPE_DETECTION,
            True,
            {
                "plagiarism_analysis": {
                    "suspected_idea_plagiarism": suspected_idea_plagiarism,
                    "suspected_text_plagiarism": suspected_text_plagiarism,
                    "suspected_overall_plagiarism": suspected_overall_plagiarism,
                    "total_plagiarism_cases": len(suspected_idea_plagiarism) + len(suspected_text_plagiarism) + len(suspected_overall_plagiarism)
                }
            }
        )

    # ========================================================================
    # 步骤8: 过度引用检测
    # ========================================================================

    def _step8_over_citation_detection(self) -> StepResult:
        """
        步骤8: 检测过度引用

        输入: segments, citations
        输出:
            - over_citation_segments: 过度引用片段列表
        """
        print("  📚 过度引用检测...")

        segments = self.workflow_data.get("segments", [])
        citations = self.workflow_data.get("citations", [])
        over_citation_segments = []

        for segment in segments:
            segment_content = segment["content"]

            # 检测过度引用
            is_over_citation = self.detector._detect_over_citation(
                segment_content, citations
            )

            if is_over_citation:
                over_citation_segments.append({
                    "location": segment["location"],
                    "citation_count": segment_content.count('[') + segment_content.count('('),
                    "content": segment_content[:150] + "..." if len(segment_content) > 150 else segment_content
                })

        print(f"  ✅ 完成 {len(segments)} 个片段的引用检测")
        print(f"     - 过度引用片段: {len(over_citation_segments)} 个")

        return StepResult(
            DetectionStep.OVER_CITATION_DETECTION,
            True,
            {
                "over_citation_segments": over_citation_segments,
                "over_citation_count": len(over_citation_segments)
            }
        )

    # ========================================================================
    # 步骤9: 相似内容检测（表格、公式）
    # ========================================================================

    def _step9_similar_objects_detection(self) -> StepResult:
        """
        步骤9: 检测相似表格和公式

        检测项:
            1. 相似表格
            2. 相似公式

        输入: content
        输出:
            - similar_objects: 相似对象检测结果
        """
        print("  📊 相似内容检测（表格、公式）...")

        content = self.workflow_data.get("content", "")
        similar_objects = self.detector._detect_similar_objects(content)

        print(f"  ✅ 完成相似内容检测:")
        print(f"     - 表格数量: {similar_objects['table_count']}")
        print(f"     - 公式数量: {similar_objects['formula_count']}")
        if similar_objects.get('similar_tables'):
            print(f"     - 疑似相似表格: {len(similar_objects['similar_tables'])} 项")
        if similar_objects.get('similar_formulas'):
            print(f"     - 疑似相似公式: {len(similar_objects['similar_formulas'])} 项")

        return StepResult(
            DetectionStep.SIMILAR_OBJECTS_DETECTION,
            True,
            {"similar_objects": similar_objects}
        )

    # ========================================================================
    # 步骤10: 增强AI检测（3项）
    # ========================================================================

    def _step10_enhanced_ai_detection(self) -> StepResult:
        """
        步骤10: 执行增强AI检测（3项检测）

        检测项:
            1. AI词汇密度检测
            2. 句式突发性检测
            3. 改写攻击检测

        输入: content
        输出:
            - enhanced_ai_results: 增强AI检测结果
        """
        print("  🔬 增强AI检测（3项）...")

        from ai_paper_detector import EnhancedAIDetector

        content = self.workflow_data.get("content", "")

        # 1. AI词汇密度检测
        print("     1️⃣ AI词汇密度检测...")
        vocab_result = EnhancedAIDetector.detect_vocabulary_density(content)
        print(f"        ✅ 密度: {vocab_result['density_per_1000']} 个/1000字 ({vocab_result['risk_level']})")

        # 2. 句式突发性检测
        print("     2️⃣ 句式突发性检测...")
        burstiness_result = EnhancedAIDetector.detect_burstiness(content)
        print(f"        ✅ 变异系数: {burstiness_result['cv']} ({burstiness_result['risk_level']})")

        # 3. 改写攻击检测
        print("     3️⃣ 改写攻击检测...")
        paraphrasing_result = EnhancedAIDetector.detect_paraphrasing(content)
        print(f"        ✅ 风险等级: {paraphrasing_result['risk_level']}")

        # 综合检测
        comprehensive_result = EnhancedAIDetector.comprehensive_detection(content)

        print(f"  ✅ 完成3项增强AI检测")
        print(f"     - 综合风险: {comprehensive_result['overall_risk']}")

        return StepResult(
            DetectionStep.ENHANCED_AI_DETECTION,
            True,
            {
                "enhanced_ai_results": {
                    "vocabulary": vocab_result,
                    "burstiness": burstiness_result,
                    "paraphrasing": paraphrasing_result,
                    "comprehensive": comprehensive_result
                }
            }
        )

    # ========================================================================
    # 步骤11: 统计指标计算
    # ========================================================================

    def _step11_metrics_calculation(self) -> StepResult:
        """
        步骤11: 计算所有统计指标

        计算项:
            1. 知网指标（4项）
            2. 维普指标（3项）
            3. 字数统计（8项）
            4. 百分比划分（2项）

        输入: 所有之前的检测结果
        输出:
            - metrics: 完整的统计指标
        """
        print("  📊 统计指标计算...")

        # 收集数据
        segments = self.workflow_data.get("segments", [])
        similarity_results = self.workflow_data.get("similarity_results", [])
        aigc_results = self.workflow_data.get("aigc_results", [])
        citations = self.workflow_data.get("citations", [])
        paper_info = self.workflow_data.get("paper_info", {})
        distribution = self.workflow_data.get("distribution", {})
        plagiarism_analysis = self.workflow_data.get("plagiarism_analysis", {})
        similar_objects = self.workflow_data.get("similar_objects", {})

        # 计算各项指标
        total_words = 0
        total_similarity_score = 0
        total_aigc_score = 0
        duplicate_words = 0
        suspected_segment_count = 0
        max_single_duplicate = 0
        max_single_duplicate_location = ""
        front_words = 0
        front_duplicate_words = 0
        suspected_max_overlap = 0
        suspected_min_overlap = float('inf')

        # 维普指标
        cited_words = 0
        copied_words = 0
        original_words = 0

        # 统计相似片段
        similar_segments = []

        for i, (sim_result, aigc_result) in enumerate(zip(similarity_results, aigc_results)):
            segment = sim_result["segment"]
            segment_content = segment["content"]
            word_count = segment["word_count"]

            similarity_score = sim_result["similarity_score"]
            aigc_score = aigc_result["aigc_score"]

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

            # 重复字数统计
            if similarity_score >= 30:
                segment_duplicate = int(word_count * similarity_score / 100)
                duplicate_words += segment_duplicate
                suspected_segment_count += 1

                # 更新疑似段落重合字数
                if segment_duplicate > suspected_max_overlap:
                    suspected_max_overlap = segment_duplicate
                if segment_duplicate < suspected_min_overlap:
                    suspected_min_overlap = segment_duplicate

                # 单篇最大重复
                if segment_duplicate > max_single_duplicate:
                    max_single_duplicate = segment_duplicate
                    max_single_duplicate_location = segment["location"]

                # 前部重合（前30%）
                if i < len(segments) * 0.3:
                    front_words += word_count
                    front_duplicate_words += segment_duplicate

                # 保存相似片段
                similar_segments.append({
                    "location": segment["location"],
                    "similarity": f"{similarity_score:.1f}%",
                    "word_count": word_count,
                    "overlap_words": segment_duplicate,
                    "source_type": sim_result["analysis"]["potential_sources"][0] if sim_result["analysis"]["potential_sources"] else "未知",
                    "summary": segment_content[:100] + "..." if len(segment_content) > 100 else segment_content
                })

            # 前部字数统计
            if i < len(segments) * 0.3:
                front_words += word_count

        # 修正疑似段落最小重合字数
        if suspected_min_overlap == float('inf'):
            suspected_min_overlap = 0

        # 计算总体指标
        avg_similarity = total_similarity_score / total_words if total_words > 0 else 0
        avg_aigc = total_aigc_score / total_words if total_words > 0 else 0

        # 去除引用后的相似度
        citation_ratio = len(citations) / len(segments) if segments else 0
        similarity_without_citations = max(avg_similarity - citation_ratio * 5, 0)
        similarity_without_self = avg_similarity  # 暂无自我发表检测

        # 单篇最大文字复制比
        max_single_similarity_ratio = (max_single_duplicate / total_words * 100) if total_words > 0 else 0

        # 百分比划分
        copy_part_percentage = (duplicate_words / total_words * 100) if total_words > 0 else 0
        no_problem_percentage = 100 - copy_part_percentage

        # 维普指标
        citation_rate = (cited_words / total_words * 100) if total_words > 0 else 0
        copy_rate = (copied_words / total_words * 100) if total_words > 0 else 0
        original_rate = (original_words / total_words * 100) if total_words > 0 else 0

        # AIGC分析
        aigc_analysis = {
            "total_rate": f"{avg_aigc:.1f}%",
            "risk_level": self.detector._get_overall_risk_level(avg_aigc),
            "chapter_rates": self.detector._calculate_chapter_rates(
                segments, self.workflow_data.get("sections", {})
            ),
            "high_risk_segments": [
                {
                    "location": r["segment"]["location"],
                    "rate": f"{r['aigc_score']:.1f}%",
                    "risk_factors": ", ".join(r["detection"]["risk_factors"]),
                    "content": r["segment"]["content"][:150] + "..." if len(r["segment"]["content"]) > 150 else r["segment"]["content"]
                }
                for r in aigc_results if r["aigc_score"] >= 15
            ],
            "suggestions": self.detector._generate_overall_suggestions(avg_aigc)
        }

        print(f"  ✅ 完成所有统计指标计算:")
        print(f"     - 总字数: {total_words}")
        print(f"     - 总文字复制比: {avg_similarity:.1f}%")
        print(f"     - AIGC生成率: {avg_aigc:.1f}%")
        print(f"     - 重复字数: {duplicate_words}")
        print(f"     - 疑似段落数: {suspected_segment_count}")

        return StepResult(
            DetectionStep.METRICS_CALCULATION,
            True,
            {
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

                    # 字数统计（8项）
                    "total_words": total_words,
                    "total_segments": len(segments),
                    "duplicate_words": duplicate_words,
                    "suspected_segment_count": suspected_segment_count,
                    "max_single_duplicate_words": max_single_duplicate,
                    "max_single_duplicate_location": max_single_duplicate_location,
                    "front_overlap_words": front_duplicate_words,
                    "suspected_max_overlap_words": suspected_max_overlap,
                    "suspected_min_overlap_words": suspected_min_overlap,

                    # 百分比划分
                    "copy_part_percentage": f"{copy_part_percentage:.1f}%",
                    "no_problem_percentage": f"{no_problem_percentage:.1f}%",

                    # 其他
                    "aigc_rate": f"{avg_aigc:.1f}%",
                    "distribution": distribution,
                    "similar_segments": similar_segments,
                    "plagiarism_analysis": plagiarism_analysis,
                    "similar_objects": similar_objects,
                    "aigc_analysis": aigc_analysis
                },
                "paper_info": paper_info
            }
        )

    # ========================================================================
    # 步骤12: 报告生成
    # ========================================================================

    def _step12_report_generation(self) -> StepResult:
        """
        步骤12: 生成检测报告

        报告类型:
            1. 简洁版报告
            2. 全文版报告
            3. AIGC专项报告

        输入: detection_results, paper_info
        输出:
            - reports: 生成的报告
        """
        print("  📋 生成检测报告...")

        detection_results = self.workflow_data.get("detection_results", {})
        paper_info = self.workflow_data.get("paper_info", {})

        # 这里只是标记报告生成步骤，实际报告生成在主流程中
        print(f"  ✅ 报告生成准备完成")
        print(f"     - 简洁版报告: 包含核心指标")
        print(f"     - 全文版报告: 包含详细分析")
        print(f"     - AIGC专项报告: 包含AI检测详情")

        return StepResult(
            DetectionStep.REPORT_GENERATION,
            True,
            {
                "ready_for_report": True,
                "has_detection_results": bool(detection_results),
                "has_paper_info": bool(paper_info)
            }
        )

    # ========================================================================
    # 工具方法
    # ========================================================================

    def _get_workflow_summary(self) -> Dict:
        """获取工作流摘要"""
        return {
            "total_steps": len(self.REQUIRED_STEPS),
            "completed_steps": len(self.results),
            "success_rate": sum(1 for r in self.results if r.success) / len(self.results) if self.results else 0,
            "steps_summary": [r.to_dict() for r in self.results],
            "start_time": self.results[0].timestamp.strftime("%Y-%m-%d %H:%M:%S") if self.results else None,
            "end_time": self.results[-1].timestamp.strftime("%Y-%m-%d %H:%M:%S") if self.results else None
        }

    def print_workflow_summary(self):
        """打印工作流摘要"""
        print()
        print("=" * 70)
        print("📊 检测流程摘要")
        print("=" * 70)

        for i, result in enumerate(self.results, 1):
            status = "✅" if result.success else "❌"
            print(f"{status} 步骤 {i}: {result.step.name}")
            if result.error:
                print(f"   错误: {result.error}")

        print()
        print(f"总计: {len(self.results)} 个步骤完成")


class WorkflowError(Exception):
    """工作流错误"""

    def __init__(self, message: str, step: DetectionStep, result: StepResult):
        super().__init__(message)
        self.step = step
        self.result = result


# 导入必要的常量
MIN_SEGMENT_LENGTH = 100
MAX_SEGMENT_LENGTH = 2000


def main():
    """测试工作流"""
    print("Paper Detection Workflow - 检测流程编排器")
    print()


if __name__ == "__main__":
    main()
