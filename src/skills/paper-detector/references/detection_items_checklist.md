# 论文检测项清单

> 本文档列出所有强制执行的检测项，用于快速查阅和验证。

## 📋 使用说明

- ✅ = 必须检测（强制）
- ⭐ = 可选检测（增强）
- 📊 = 统计指标
- 🔍 = 检测分析

---

## 🎯 核心检测项（29项）

### 1️⃣ 知网指标（4项）

| 序号 | 检测项 | 说明 | 输出位置 |
|------|--------|------|----------|
| 1 | ✅ 总文字复制比 | 整体相似度百分比 | `detection_results.total_similarity` |
| 2 | ✅ 去除引用文献复制比 | 排除引用后的相似度 | `detection_results.similarity_without_citations` |
| 3 | ✅ 去除本人已发表文献复制比 | 排除自我引用的相似度 | `detection_results.similarity_without_self` |
| 4 | ✅ 单篇最大文字复制比 | 单个片段最高相似度占比 | `detection_results.max_single_similarity_ratio` |

**执行步骤**: 步骤11（统计指标计算）

---

### 2️⃣ 维普指标（3项）

| 序号 | 检测项 | 说明 | 输出位置 |
|------|--------|------|----------|
| 5 | ✅ 引用率 | 正确引用内容占比 | `detection_results.citation_rate` |
| 6 | ✅ 复写率 | 相似度≥50%内容占比 | `detection_results.copy_rate` |
| 7 | ✅ 自写率 | 相似度<30%原创内容占比 | `detection_results.original_rate` |

**关系**: 引用率 + 复写率 + 自写率 ≈ 100%

**执行步骤**: 步骤11（统计指标计算）

---

### 3️⃣ 字数统计（8项）

| 序号 | 检测项 | 说明 | 输出位置 |
|------|--------|------|----------|
| 8 | ✅ 总字数 | 论文总字符数（知网标准） | `detection_results.total_words` |
| 9 | ✅ 总段落数 | 检测的段落总数 | `detection_results.total_segments` |
| 10 | ✅ 重复字数 | 相似度≥30%段落按比例累加 | `detection_results.duplicate_words` |
| 11 | ✅ 疑似段落数 | 相似度≥30%的段落数量 | `detection_results.suspected_segment_count` |
| 12 | ✅ 单篇最大重复字数 | 单个片段最大重复字数 | `detection_results.max_single_duplicate_words` |
| 13 | ✅ 单篇最大重复位置 | 最大重复字数所在位置 | `detection_results.max_single_duplicate_location` |
| 14 | ✅ 前部重合字数 | 前30%内容的重复字数 | `detection_results.front_overlap_words` |
| 15 | ✅ 疑似段落最大重合字数 | 疑似段落中最大重合字数 | `detection_results.suspected_max_overlap_words` |
| 16 | ✅ 疑似段落最小重合字数 | 疑似段落中最小重合字数 | `detection_results.suspected_min_overlap_words` |

**执行步骤**: 步骤11（统计指标计算）

---

### 4️⃣ 百分比划分（2项）

| 序号 | 检测项 | 说明 | 输出位置 |
|------|--------|------|----------|
| 17 | ✅ 文字复制部分 | (重复字数/总字数)×100% | `detection_results.copy_part_percentage` |
| 18 | ✅ 无问题部分 | 100% - 文字复制部分 | `detection_results.no_problem_percentage` |

**关系**: 文字复制部分 + 无问题部分 = 100%

**执行步骤**: 步骤11（统计指标计算）

---

### 5️⃣ 剽窃类型检测（4种）

| 序号 | 检测项 | 说明 | 输出位置 |
|------|--------|------|----------|
| 19 | ✅ 疑似剽窃观点 | 论点结构相似（30-40%） | `detection_results.plagiarism_analysis.suspected_idea_plagiarism` |
| 20 | ✅ 疑似剽窃文字表述 | 文字高度相似（40-60%） | `detection_results.plagiarism_analysis.suspected_text_plagiarism` |
| 21 | ✅ 疑似整体剽窃 | 大段内容相似（≥60%） | `detection_results.plagiarism_analysis.suspected_overall_plagiarism` |
| 22 | ✅ 过度引用 | 引用密度过高（>3个/100字） | `detection_results.plagiarism_analysis.over_citation_segments` |

**执行步骤**:
- 剽窃类型：步骤7（剽窃类型检测）
- 过度引用：步骤8（过度引用检测）

---

### 6️⃣ 相似内容检测（2类）

| 序号 | 检测项 | 说明 | 输出位置 |
|------|--------|------|----------|
| 23 | ✅ 相似表格 | 重复的表格引用 | `detection_results.similar_objects.similar_tables` |
| 24 | ✅ 相似公式 | 重复的公式引用 | `detection_results.similar_objects.similar_formulas` |

**执行步骤**: 步骤9（相似内容检测）

---

### 7️⃣ AIGC检测（2项）

| 序号 | 检测项 | 说明 | 输出位置 |
|------|--------|------|----------|
| 25 | ✅ AIGC总体生成率 | 整体AI生成概率 | `detection_results.aigc_rate` |
| 26 | ✅ 各章节AIGC生成率 | 分章节生成概率 | `detection_results.aigc_analysis.chapter_rates` |

**执行步骤**: 步骤6（AIGC检测）

---

### 8️⃣ 增强AI检测（3项）⭐

| 序号 | 检测项 | 说明 | 输出位置 |
|------|--------|------|----------|
| 27 | ⭐ AI词汇密度 | AI高频词汇使用频率（个/1000字） | `enhanced_ai_results.vocabulary.density_per_1000` |
| 28 | ⭐ 句式突发性 | 句子长度变化程度（变异系数CV） | `enhanced_ai_results.burstiness.cv` |
| 29 | ⭐ 改写攻击 | AI改写工具使用痕迹 | `enhanced_ai_results.paraphrasing.risk_level` |

**执行步骤**: 步骤10（增强AI检测）[可选]

---

## 📊 检测步骤与检测项映射

| 步骤 | 名称 | 检测项数 | 检测项列表 |
|------|------|----------|-----------|
| 1 | 文档读取与预处理 | - | 提供基础数据 |
| 2 | 章节提取 | - | 识别章节结构 |
| 3 | 文本分割 | - | 生成检测片段 |
| 4 | 引用识别 | - | 识别引用标记 |
| 5 | 相似度检测 | - | 计算各片段相似度 |
| 6 | AIGC检测 | 2 | AIGC总体生成率、各章节生成率 |
| 7 | 剽窃类型检测 | 3 | 观点剽窃、文字剽窃、整体剽窃 |
| 8 | 过度引用检测 | 1 | 过度引用 |
| 9 | 相似内容检测 | 2 | 相似表格、相似公式 |
| 10 | 增强AI检测 ⭐ | 3 | 词汇密度、突发性、改写攻击 |
| 11 | 统计指标计算 | 17 | 知网4、维普3、字数8、百分比2 |
| 12 | 报告生成 | - | 生成3种报告 |

**总计**: 26项核心检测 + 3项可选检测 = 29项

---

## ✅ 检测完整性验证

### 使用工作流模式（推荐）

```python
from ai_paper_detector import AIPaperDetector

detector = AIPaperDetector()
result = detector.analyze_paper("paper.md", use_workflow=True)

# 验证所有检测项都存在
required_items = [
    # 知网指标 (4)
    "total_similarity",
    "similarity_without_citations",
    "similarity_without_self",
    "max_single_similarity_ratio",

    # 维普指标 (3)
    "citation_rate",
    "copy_rate",
    "original_rate",

    # 字数统计 (8)
    "total_words",
    "total_segments",
    "duplicate_words",
    "suspected_segment_count",
    "max_single_duplicate_words",
    "max_single_duplicate_location",
    "front_overlap_words",
    "suspected_max_overlap_words",
    "suspected_min_overlap_words",

    # 百分比划分 (2)
    "copy_part_percentage",
    "no_problem_percentage",

    # AIGC (2)
    "aigc_rate",

    # 其他
    "distribution",
    "similar_segments",
    "plagiarism_analysis",
    "similar_objects",
    "aigc_analysis"
]

detection_results = result["detection_results"]

missing_items = []
for item in required_items:
    if item not in detection_results:
        missing_items.append(item)

if missing_items:
    print(f"❌ 缺少检测项: {missing_items}")
else:
    print("✅ 所有核心检测项都已执行")
```

### 命令行快速验证

```bash
# 运行检测
python3 scripts/ai_paper_detector.py paper.md

# 检查输出JSON文件
python3 -c "
import json
import sys

with open('detection_result_*.json', 'r') as f:
    result = json.load(f)

detection_results = result.get('detection_results', {})

# 检查核心检测项
core_items = [
    'total_similarity',
    'citation_rate',
    'copy_rate',
    'original_rate',
    'total_words',
    'duplicate_words',
    'aigc_rate'
]

missing = [item for item in core_items if item not in detection_results]

if missing:
    print(f'❌ 缺少: {missing}')
    sys.exit(1)
else:
    print('✅ 核心检测项完整')
    sys.exit(0)
"
```

---

## 📈 检测报告模板

### 简洁版报告

```
✅ 知网指标 (4项)
  - 总文字复制比
  - 去除引用文献复制比
  - 去除本人已发表文献复制比
  - 单篇最大文字复制比

✅ 维普指标 (3项)
  - 引用率
  - 复写率
  - 自写率

✅ 字数统计 (8项)
  - 总字数
  - 总段落数
  - 重复字数
  - 疑似段落数
  - 单篇最大重复字数
  - 单篇最大重复位置
  - 前部重合字数
  - 疑似段落最大/最小重合字数

✅ 百分比划分 (2项)
  - 文字复制部分
  - 无问题部分

✅ 剽窃类型 (4种)
  - 疑似剽窃观点: X 处
  - 疑似剽窃文字表述: X 处
  - 疑似整体剽窃: X 处
  - 过度引用: X 处

✅ 相似度分布表
  - ≥50%: X 个片段, X 字
  - 40%-50%: X 个片段, X 字
  - 30%-40%: X 个片段, X 字
  - <30%: X 个片段, X 字
```

### 全文版报告

包含简洁版的所有内容，以及：
- ✅ 相似片段详情列表
- ✅ 剽窃类型检测详情（每种剽窃的具体案例）
- ✅ 过度引用详情
- ✅ 相似内容检测详情（表格、公式）
- ✅ AIGC检测详细分析（高风险段落）

### AIGC专项报告

- ✅ 基本信息
- ✅ AIGC检测结果汇总
- ✅ 各章节AIGC生成率统计表
- ✅ 高风险段落详情
- ✅ 修改建议

---

## 🔗 相关文档

- **流程规范**: `detection_workflow.md`
- **系统架构**: `detection_flow_architecture.md`
- **快速指南**: `quick_start_workflow.md`
- **检测标准**: `detection_criteria.md`

---

**维护者**: Paper Detector Team
**更新时间**: 2025-02-07
**版本**: 2.0
