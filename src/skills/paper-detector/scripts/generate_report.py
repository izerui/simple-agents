#!/usr/bin/env python3
"""
Paper Detector - 生成论文检测报告

根据分析结果生成格式化的检测报告

核心指标说明：
- 文字复制部分 = (重复字数 / 总字数) × 100%
- 无问题部分 = 100% - 文字复制部分
- 这两个指标基于实际重复字数统计，而非加权平均相似度
"""

import sys
from datetime import datetime
from typing import Dict, List
import json


class PaperDetectionReport:
    """论文检测报告生成器"""

    def __init__(self, paper_info: Dict, detection_results: Dict = None):
        """
        初始化报告生成器

        Args:
            paper_info: 论文基本信息
            detection_results: 检测结果数据
        """
        self.paper_info = paper_info
        self.detection_results = detection_results or {}
        self.detection_id = self._generate_id()
        self.detection_time = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")

    def _generate_id(self) -> str:
        """生成检测编号"""
        import random
        now = datetime.now()
        return f"PD{now.strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"

    def generate_simple_report(self) -> str:
        """
        生成简洁版报告

        Returns:
            报告文本
        """
        lines = []
        lines.append("# 论文检测报告（简洁版）")
        lines.append("")
        lines.append("## 基本信息")
        lines.append(f"- 论文题目：《{self.paper_info.get('title', '未知')}》")
        lines.append(f"- 作者：{self.paper_info.get('author', '未知')}")
        lines.append(f"- 检测时间：{self.detection_time}")
        lines.append(f"- 检测编号：{self.detection_id}")
        lines.append("")
        lines.append("## 检测结果汇总")
        lines.append(f"- 原文总字数：{self.paper_info.get('word_count', 0)}字")
        lines.append("")

        # 知网核心指标
        lines.append("**知网指标**")
        lines.append(f"- 总文字复制比：{self.detection_results.get('total_similarity', 'N/A')}")
        lines.append(f"- 去除引用文献复制比：{self.detection_results.get('similarity_without_citations', 'N/A')}")
        lines.append(f"- 去除本人已发表文献复制比：{self.detection_results.get('similarity_without_self', 'N/A')}")
        if 'max_single_similarity_ratio' in self.detection_results:
            lines.append(f"- 单篇最大文字复制比：{self.detection_results.get('max_single_similarity_ratio', 'N/A')}")
        lines.append("")

        # 维普核心指标
        if 'citation_rate' in self.detection_results:
            lines.append("**维普指标**")
            lines.append(f"- 引用率：{self.detection_results.get('citation_rate', 'N/A')}（正确引用内容占比）")
            lines.append(f"- 复写率：{self.detection_results.get('copy_rate', 'N/A')}（相似度≥50%内容占比）")
            lines.append(f"- 自写率：{self.detection_results.get('original_rate', 'N/A')}（相似度<30%原创内容占比）")
            lines.append("")

        if 'aigc_rate' in self.detection_results:
            lines.append(f"- AIGC总体生成率：{self.detection_results.get('aigc_rate', 'N/A')}")

        if 'copy_part_percentage' in self.detection_results:
            lines.append(f"- 文字复制部分：{self.detection_results.get('copy_part_percentage', 'N/A')}（基于重复字数计算）")
            lines.append(f"- 无问题部分：{self.detection_results.get('no_problem_percentage', 'N/A')}（100% - 文字复制部分）")
        lines.append("")

        # 字数统计详情
        if 'duplicate_words' in self.detection_results:
            lines.append("## 字数统计")
            lines.append(f"- 总字数：{self.detection_results.get('total_words', 'N/A')}")
            lines.append(f"- 总段落数：{self.detection_results.get('total_segments', 'N/A')}")
            lines.append(f"- 重复字数：{self.detection_results.get('duplicate_words', 'N/A')}")
            lines.append(f"- 疑似段落数：{self.detection_results.get('suspected_segment_count', 'N/A')}")
            if 'max_single_duplicate_words' in self.detection_results:
                lines.append(f"- 单篇最大重复字数：{self.detection_results.get('max_single_duplicate_words', 'N/A')} ({self.detection_results.get('max_single_duplicate_location', 'N/A')})")
            lines.append(f"- 前部重合字数：{self.detection_results.get('front_overlap_words', 'N/A')}")
            if self.detection_results.get('suspected_segment_count', 0) > 0:
                lines.append(f"- 疑似段落最大重合字数：{self.detection_results.get('suspected_max_overlap_words', 'N/A')}")
                lines.append(f"- 疑似段落最小重合字数：{self.detection_results.get('suspected_min_overlap_words', 'N/A')}")
            lines.append("")

        lines.append("## 相似度分布")
        lines.append("| 相似度区间 | 段落数 | 字数 |")
        lines.append("|-----------|--------|------|")

        distribution = self.detection_results.get('distribution', {})
        for range_name in ['≥50%', '40%-50%', '30%-40%', '<30%']:
            data = distribution.get(range_name, {'count': 0, 'words': 0})
            lines.append(f"| {range_name} | {data['count']} | {data['words']} |")

        lines.append("")

        # 剽窃类型检测
        if 'plagiarism_analysis' in self.detection_results:
            plagiarism = self.detection_results['plagiarism_analysis']
            if plagiarism.get('total_plagiarism_cases', 0) > 0:
                lines.append("## 剽窃类型检测")
                lines.append(f"- 疑似剽窃观点：{len(plagiarism.get('suspected_idea_plagiarism', []))} 处")
                lines.append(f"- 疑似剽窃文字表述：{len(plagiarism.get('suspected_text_plagiarism', []))} 处")
                lines.append(f"- 疑似整体剽窃：{len(plagiarism.get('suspected_overall_plagiarism', []))} 处")
                lines.append(f"- 过度引用：{plagiarism.get('over_citation_count', 0)} 处")
                lines.append("")

        lines.append("---")
        lines.append("*本报告由AI辅助生成，检测结果仅供参考，不代表最终学术评定。*")

        return "\n".join(lines)

    def generate_full_report(self) -> str:
        """
        生成全文版报告

        Returns:
            报告文本
        """
        lines = []
        lines.append("# 论文检测报告（全文版）")
        lines.append("")
        lines.append("## 基本信息")
        lines.append(f"- 论文题目：《{self.paper_info.get('title', '未知')}》")
        lines.append(f"- 作者：{self.paper_info.get('author', '未知')}")
        lines.append(f"- 检测时间：{self.detection_time}")
        lines.append(f"- 检测编号：{self.detection_id}")
        lines.append("")
        lines.append("## 检测结果汇总")
        lines.append(f"- 原文总字数：{self.paper_info.get('word_count', 0)}字")
        lines.append("")

        # 知网核心指标
        lines.append("**知网指标**")
        lines.append(f"- 总文字复制比：{self.detection_results.get('total_similarity', 'N/A')}")
        lines.append(f"- 去除引用文献复制比：{self.detection_results.get('similarity_without_citations', 'N/A')}")
        lines.append(f"- 去除本人已发表文献复制比：{self.detection_results.get('similarity_without_self', 'N/A')}")
        if 'max_single_similarity_ratio' in self.detection_results:
            lines.append(f"- 单篇最大文字复制比：{self.detection_results.get('max_single_similarity_ratio', 'N/A')}")
        lines.append("")

        # 维普核心指标
        if 'citation_rate' in self.detection_results:
            lines.append("**维普指标**")
            lines.append(f"- 引用率：{self.detection_results.get('citation_rate', 'N/A')}（正确引用内容占比）")
            lines.append(f"- 复写率：{self.detection_results.get('copy_rate', 'N/A')}（相似度≥50%内容占比）")
            lines.append(f"- 自写率：{self.detection_results.get('original_rate', 'N/A')}（相似度<30%原创内容占比）")
            lines.append("")

        if 'aigc_rate' in self.detection_results:
            lines.append(f"- AIGC总体生成率：{self.detection_results.get('aigc_rate', 'N/A')}")

        if 'copy_part_percentage' in self.detection_results:
            lines.append(f"- 文字复制部分：{self.detection_results.get('copy_part_percentage', 'N/A')}（基于重复字数计算）")
            lines.append(f"- 无问题部分：{self.detection_results.get('no_problem_percentage', 'N/A')}（100% - 文字复制部分）")
        lines.append("")

        # 字数统计详情
        if 'duplicate_words' in self.detection_results:
            lines.append("## 字数统计")
            lines.append(f"- 总字数：{self.detection_results.get('total_words', 'N/A')}")
            lines.append(f"- 总段落数：{self.detection_results.get('total_segments', 'N/A')}")
            lines.append(f"- 重复字数：{self.detection_results.get('duplicate_words', 'N/A')}")
            lines.append(f"- 疑似段落数：{self.detection_results.get('suspected_segment_count', 'N/A')}")
            if 'max_single_duplicate_words' in self.detection_results:
                lines.append(f"- 单篇最大重复字数：{self.detection_results.get('max_single_duplicate_words', 'N/A')} ({self.detection_results.get('max_single_duplicate_location', 'N/A')})")
            lines.append(f"- 前部重合字数：{self.detection_results.get('front_overlap_words', 'N/A')}")
            if self.detection_results.get('suspected_segment_count', 0) > 0:
                lines.append(f"- 疑似段落最大重合字数：{self.detection_results.get('suspected_max_overlap_words', 'N/A')}")
                lines.append(f"- 疑似段落最小重合字数：{self.detection_results.get('suspected_min_overlap_words', 'N/A')}")
            lines.append("")

        lines.append("## 相似度分布")
        lines.append("| 相似度区间 | 段落数 | 字数 |")
        lines.append("|-----------|--------|------|")

        distribution = self.detection_results.get('distribution', {})
        for range_name in ['≥50%', '40%-50%', '30%-40%', '<30%']:
            data = distribution.get(range_name, {'count': 0, 'words': 0})
            lines.append(f"| {range_name} | {data['count']} | {data['words']} |")

        lines.append("")

        # 剽窃类型检测
        if 'plagiarism_analysis' in self.detection_results:
            plagiarism = self.detection_results['plagiarism_analysis']
            if plagiarism.get('total_plagiarism_cases', 0) > 0 or plagiarism.get('over_citation_count', 0) > 0:
                lines.append("## 剽窃类型检测")
                lines.append(f"- 疑似剽窃观点：{len(plagiarism.get('suspected_idea_plagiarism', []))} 处")
                lines.append(f"- 疑似剽窃文字表述：{len(plagiarism.get('suspected_text_plagiarism', []))} 处")
                lines.append(f"- 疑似整体剽窃：{len(plagiarism.get('suspected_overall_plagiarism', []))} 处")
                lines.append(f"- 过度引用：{plagiarism.get('over_citation_count', 0)} 处")
                lines.append("")

                # 详细列表
                if plagiarism.get('suspected_idea_plagiarism'):
                    lines.append("### 疑似剽窃观点详情")
                    for i, item in enumerate(plagiarism['suspected_idea_plagiarism'], 1):
                        lines.append(f"\n#### 案例 {i}")
                        lines.append(f"- **位置**: {item.get('location', '未知')}")
                        lines.append(f"- **描述**: {item.get('description', '')}")
                        lines.append(f"- **置信度**: {item.get('confidence', 'N/A')}")
                        lines.append(f"- **内容**: {item.get('content', '')[:100]}...")
                    lines.append("")

                if plagiarism.get('over_citation_segments'):
                    lines.append("### 过度引用详情")
                    for i, item in enumerate(plagiarism['over_citation_segments'], 1):
                        lines.append(f"\n#### 片段 {i}")
                        lines.append(f"- **位置**: {item.get('location', '未知')}")
                        lines.append(f"- **引用数量**: {item.get('citation_count', 0)}")
                        lines.append(f"- **内容**: {item.get('content', '')[:100]}...")
                    lines.append("")

        # 相似内容检测（表格、公式）
        if 'similar_objects' in self.detection_results:
            similar_objects = self.detection_results['similar_objects']
            if similar_objects.get('table_count', 0) > 0 or similar_objects.get('formula_count', 0) > 0:
                lines.append("## 相似内容检测")
                lines.append(f"- 表格数量：{similar_objects.get('table_count', 0)}")
                lines.append(f"- 公式数量：{similar_objects.get('formula_count', 0)}")
                if similar_objects.get('similar_tables'):
                    lines.append(f"- 疑似相似表格：{len(similar_objects['similar_tables'])} 项")
                    for item in similar_objects['similar_tables']:
                        lines.append(f"  - {item.get('issue', '')} (重复 {item.get('count', 0)} 次)")
                if similar_objects.get('similar_formulas'):
                    lines.append(f"- 疑似相似公式：{len(similar_objects['similar_formulas'])} 项")
                    for item in similar_objects['similar_formulas']:
                        lines.append(f"  - {item.get('issue', '')} (重复 {item.get('count', 0)} 次)")
                lines.append("")

        lines.append("## 相似片段详情")

        similar_segments = self.detection_results.get('similar_segments', [])
        if similar_segments:
            for i, segment in enumerate(similar_segments, 1):
                lines.append(f"\n### 片段 {i}")
                lines.append(f"- **位置**: {segment.get('location', '未知')}")
                lines.append(f"- **相似度**: {segment.get('similarity', 'N/A')}")
                lines.append(f"- **字数**: {segment.get('word_count', 0)}")
                lines.append(f"- **来源类型**: {segment.get('source_type', '未知')}")
                lines.append(f"- **内容摘要**: {segment.get('summary', segment.get('content', '')[:100])}")
        else:
            lines.append("\n未检测到明显的相似片段。")

        if 'aigc_analysis' in self.detection_results:
            lines.append("")
            lines.append("## AIGC检测分析")
            aigc = self.detection_results['aigc_analysis']
            lines.append(f"- **总体生成率**: {aigc.get('total_rate', 'N/A')}")
            lines.append(f"- **风险等级**: {aigc.get('risk_level', 'N/A')}")

            if 'high_risk_segments' in aigc:
                lines.append("\n### 高风险段落")
                for i, seg in enumerate(aigc['high_risk_segments'], 1):
                    lines.append(f"\n#### 段落 {i}")
                    lines.append(f"- **位置**: {seg.get('location', '未知')}")
                    lines.append(f"- **生成率**: {seg.get('rate', 'N/A')}")
                    lines.append(f"- **内容**: {seg.get('content', '')[:100]}")

        lines.append("")
        lines.append("---")
        lines.append("*本报告由AI辅助生成，检测结果仅供参考，不代表最终学术评定。*")
        lines.append("*建议结合官方检测平台（知网、维普等）进行交叉验证。*")

        return "\n".join(lines)

    def generate_aigc_report(self) -> str:
        """
        生成AIGC专项报告

        Returns:
            报告文本
        """
        lines = []
        lines.append("# AIGC检测报告")
        lines.append("")
        lines.append("## 基本信息")
        lines.append(f"- 论文题目：《{self.paper_info.get('title', '未知')}》")
        lines.append(f"- 作者：{self.paper_info.get('author', '未知')}")
        lines.append(f"- 检测时间：{self.detection_time}")
        lines.append(f"- 检测编号：{self.detection_id}")
        lines.append("")
        lines.append("## AIGC检测结果汇总")
        lines.append(f"- 原文总字数：{self.paper_info.get('word_count', 0)}字")

        aigc = self.detection_results.get('aigc_analysis', {})
        lines.append(f"- AIGC总体生成率：{aigc.get('total_rate', 'N/A')}")
        lines.append(f"- 风险等级：{aigc.get('risk_level', 'N/A')}")
        lines.append("")

        lines.append("## 各章节AIGC生成率")

        chapter_rates = aigc.get('chapter_rates', {})
        if chapter_rates:
            lines.append("| 章节 | 生成率 | 字数 |")
            lines.append("|------|--------|------|")
            for chapter, data in chapter_rates.items():
                if isinstance(data, dict):
                    rate = data.get('rate', 'N/A')
                    words = data.get('words', 0)
                else:
                    rate = data
                    words = 'N/A'
                lines.append(f"| {chapter} | {rate} | {words} |")
        else:
            lines.append("暂无章节分析数据。")

        lines.append("")
        lines.append("## 高风险段落详情")

        high_risk = aigc.get('high_risk_segments', [])
        if high_risk:
            for i, seg in enumerate(high_risk, 1):
                lines.append(f"\n### 高风险段落 {i}")
                lines.append(f"- **位置**: {seg.get('location', '未知')}")
                lines.append(f"- **生成率**: {seg.get('rate', 'N/A')}")
                lines.append(f"- **风险因素**: {seg.get('risk_factors', '未知')}")
                lines.append(f"- **内容预览**: {seg.get('content', '')[:150]}...")
        else:
            lines.append("\n未检测到高风险段落。")

        lines.append("")
        lines.append("## 修改建议")
        suggestions = aigc.get('suggestions', [
            "对高风险段落进行人工审核和修改",
            "增加个人分析和观点，减少AI生成内容",
            "补充具体的案例和数据支撑",
            "调整语言风格，使表达更加自然"
        ])
        for i, suggestion in enumerate(suggestions, 1):
            lines.append(f"{i}. {suggestion}")

        lines.append("")
        lines.append("---")
        lines.append("*本报告由AI辅助生成，检测结果仅供参考。*")

        return "\n".join(lines)

    def save_report(self, report_text: str, output_path: str):
        """
        保存报告到文件

        Args:
            report_text: 报告内容
            output_path: 输出文件路径
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report_text)
            print(f"报告已保存至: {output_path}")
        except Exception as e:
            print(f"保存报告失败: {str(e)}")


def main():
    """主函数 - 用于测试"""
    # 示例数据
    paper_info = {
        "title": "示例论文",
        "author": "张三",
        "word_count": 5000
    }

    detection_results = {
        "total_similarity": "15.5%",
        "similarity_without_citations": "12.3%",
        "similarity_without_self": "15.5%",
        "aigc_rate": "8.2%",
        "distribution": {
            "≥50%": {"count": 0, "words": 0},
            "40%-50%": {"count": 1, "words": 150},
            "30%-40%": {"count": 2, "words": 280},
            "<30%": {"count": 45, "words": 4570}
        },
        "similar_segments": [
            {
                "location": "第二章 文献综述",
                "similarity": "42%",
                "word_count": 150,
                "source_type": "学术期刊",
                "summary": "关于XXX理论的描述..."
            }
        ],
        "aigc_analysis": {
            "total_rate": "8.2%",
            "risk_level": "低风险",
            "chapter_rates": {
                "摘要": {"rate": "5%", "words": 200},
                "引言": {"rate": "12%", "words": 800},
                "正文": {"rate": "7%", "words": 3500},
                "结论": {"rate": "10%", "words": 500}
            },
            "high_risk_segments": [
                {
                    "location": "引言 第2段",
                    "rate": "35%",
                    "risk_factors": "句式规整、缺乏个人观点",
                    "content": "本研究旨在探讨..."
                }
            ],
            "suggestions": [
                "对引言部分进行人工审核和修改",
                "增加个人分析和观点"
            ]
        }
    }

    report_gen = PaperDetectionReport(paper_info, detection_results)

    print("=" * 60)
    print("论文检测报告生成测试")
    print("=" * 60)

    # 生成简洁版报告
    print("\n【简洁版报告】")
    print("-" * 40)
    print(report_gen.generate_simple_report())

    # 生成全文版报告
    print("\n【全文版报告】")
    print("-" * 40)
    print(report_gen.generate_full_report())

    # 生成AIGC报告
    print("\n【AIGC专项报告】")
    print("-" * 40)
    print(report_gen.generate_aigc_report())


if __name__ == "__main__":
    main()
