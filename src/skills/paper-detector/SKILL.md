---
name: paper-detector
description: 专业的学术论文检测工具，能够生成类似知网、维普的专业查重和AIGC检测报告。当用户需要进行论文相似度检测、生成查重报告、检测论文中的AI生成内容（AIGC）、分析引用和相似片段，或创建专业检测报告时使用此技能。支持已转换为markdown格式的论文文件。
---

# Paper Detector

专业的论文检测分析工具，能够对学术论文进行全面检测并生成类似知网、维普的专业查重和AIGC检测报告。

## Quick Start

检测论文并生成报告的基本流程：

```bash
# 1. 使用AI进行论文检测（推荐）
python3 /skills/paper-detector/scripts/ai_paper_detector.py paper.md

# 2. 生成检测报告
python3 /skills/paper-detector/scripts/generate_report.py detection_result_PDXXXXXXXXXXXX.json
```

**注意**: `ai_paper_detector.py` 是新版本的AI驱动检测工具，能够真正分析论文内容并计算相似度和AIGC生成率。

## 核心功能

### 1. 论文相似度检测

分析论文与已有文献的相似程度，识别潜在的重复或高度相似内容。

**检测指标**：

#### 知网核心指标
- **总文字复制比** - 整体相似度百分比（主要参考指标）
- **去除引用文献复制比** - 排除引用后的相似度
- **去除本人已发表文献复制比** - 排除本人已发表作品的相似度
- **单篇最大文字复制比** - 单个片段最高相似度占比

#### 维普核心指标
- **引用率** - 正确引用内容占总字数的百分比
- **复写率** - 相似度≥50%的复制内容占比（知网标准）
- **自写率** - 相似度<30%的原创内容占比

#### 字数统计（8项）
- **总字数** - 论文总字符数
- **总段落数** - 检测的段落总数
- **重复字数** - 被判定为重复的字数
- **疑似段落数** - 相似度≥30%的段落数
- **单篇最大重复字数** - 单个片段最大重复字数及位置
- **前部重合字数** - 论文前30%内容的重复字数
- **疑似段落最大重合字数** - 疑似段落中最大的重合字数
- **疑似段落最小重合字数** - 疑似段落中最小的重合字数

#### 百分比划分
- **文字复制部分百分比** - 复制内容占总字数的百分比
- **无问题部分百分比** - 原创内容占总字数的百分比

#### 剽窃类型检测（4种）
- **疑似剽窃观点** - 论点结构和逻辑与已有文献相似
- **疑似剽窃文字表述** - 文字高度相似，缺乏原创性改写
- **疑似整体剽窃** - 大段内容与已有文献高度相似
- **过度引用** - 引用密度过高或连续引用

#### 相似内容检测
- **相似表格** - 检测重复或相似的表格引用
- **相似公式** - 检测重复或相似的公式引用

**相似度等级划分**（知网标准）：
- **高相似度**（≥50%）- 红色标注，必须修改
- **中等相似度**（40%-50%）- 黄色标注，建议修改
- **低相似度**（30%-40%）- 绿色标注，注意调整
- **正常**（<30%）- 无需标注

### 2. AIGC检测（增强版）

检测论文中AI生成内容的比例，识别高风险AI生成段落。

**基础检测内容**：
- AIGC总体生成率
- 各章节/段落的AIGC生成率
- 高风险段落标注
- 风险等级评定（正常/低风险/中风险/高风险/极高风险）

**增强检测功能**（从ai文件夹整合）：

#### 2.1 AI词汇密度检测
- 检测AI高频词汇使用频率（每1000字）
- 识别连接词、形容词、动词等AI常用词
- 风险等级：>50个/1000字（高风险），30-50个/1000字（中等风险），<30个/1000字（正常）

**AI高频词汇示例**：
```
连接词：此外、同时、另外、再者、总体而言、综上所述
形容词：重要的、关键的、核心的、显著的、深刻的
动词：体现、反映、展现、表明、涵盖、包含
虚词：具有重要、提供参考、具有重要意义
```

#### 2.2 句式突发性检测
- 分析句子长度的变化程度（变异系数CV）
- 识别过于规整的句式结构（AI特征）
- 风险等级：CV<0.15（高风险），0.15-0.25（中等风险），>0.25（正常）

**检测指标**：
- 句子数量、平均长度、标准差
- 变异系数（CV）
- 相邻句子差异
- 长度范围

#### 2.3 改写攻击检测
- 检测AI改写工具的痕迹
- 识别同义词替换模式
- 评估词汇多样性和个人表达特征

**检测内容**：
- 句子结构一致性
- 改写痕迹（采用→使用，分析→探讨等）
- 个人表达特征（个人声音、数据引用、转折表达）

#### 2.4 综合AI检测
整合以上三种检测方法，提供综合评估：
- 整体风险评级
- 分项检测详情
- 修改建议

**使用方法**：
```python
import sys
sys.path.insert(0, '/skills/paper-detector/scripts')
from ai_paper_detector import EnhancedAIDetector

# 创建检测器
detector = EnhancedAIDetector()

# 1. AI词汇密度检测
vocab_result = detector.detect_vocabulary_density(text)

# 2. 句式突发性检测
burstiness_result = detector.detect_burstiness(text)

# 3. 改写攻击检测
paraphrasing_result = detector.detect_paraphrasing(text)

# 4. 综合检测（推荐）
comprehensive_result = detector.comprehensive_detection(text)
```

### 3. 剽窃类型识别

智能识别不同类型的学术不端行为：

**四种剽窃类型**：
- **观点剽窃** - 论点结构、论证逻辑相似，相似度30-40%
- **文字表述剽窃** - 文字高度相似，缺乏原创改写，相似度40-60%
- **整体剽窃** - 大段内容高度相似（>300字），相似度≥60%
- **过度引用** - 引用密度过高（每100字超过3个引用）

### 4. 相似内容检测

检测论文中的重复内容：

**检测对象**：
- 相似表格 - 识别表格引用重复
- 相似公式 - 识别公式引用重复

### 3. 引用分析

- 识别论文中的引用文献
- 分析引用的规范性和完整性
- 区分原创内容和引用内容

## 检测流程

### 方法一：使用AI自动检测（推荐）

使用 `ai_paper_detector.py` 进行完整的AI驱动检测：

```python
import sys
sys.path.insert(0, '/skills/paper-detector/scripts')
from ai_paper_detector import AIPaperDetector

# 创建检测器
detector = AIPaperDetector()

# 分析论文
result = detector.analyze_paper("论文.md")

# result 包含:
# - paper_info: 论文基本信息
# - detection_results: 完整的检测结果
#   * 核心检测结果:
#     - total_similarity: 总文字复制比
#     - similarity_without_citations: 去除引用文献复制比
#     - similarity_without_self: 去除本人已发表文献复制比
#     - max_single_similarity_ratio: 单篇最大文字复制比
#   * 字数统计:
#     - total_words: 总字数
#     - total_segments: 总段落数
#     - duplicate_words: 重复字数
#     - suspected_segment_count: 疑似段落数
#     - max_single_duplicate_words: 单篇最大重复字数
#     - max_single_duplicate_location: 单篇最大重复位置
#     - front_overlap_words: 前部重合字数
#     - suspected_max_overlap_words: 疑似段落最大重合字数
#     - suspected_min_overlap_words: 疑似段落最小重合字数
#   * 百分比划分:
#     - copy_part_percentage: 文字复制部分百分比
#     - no_problem_percentage: 无问题部分百分比
#     - aigc_rate: AIGC总体生成率
#   * distribution: 相似度分布统计
#   * similar_segments: 相似片段详情列表（含重合字数）
#   * plagiarism_analysis: 剽窃类型检测结果
#     - suspected_idea_plagiarism: 疑似剽窃观点列表
#     - suspected_text_plagiarism: 疑似剽窃文字表述列表
#     - suspected_overall_plagiarism: 疑似整体剽窃列表
#     - over_citation_segments: 过度引用段落列表
#   * similar_objects: 相似内容检测
#     - similar_tables: 相似表格列表
#     - similar_formulas: 相似公式列表
#   * aigc_analysis: AIGC检测详细分析
# - metadata: 检测元数据
```

**AI检测特点**：

1. **智能相似度分析**
   - **从0%基准开始**：完全原创的论文相似度为0%
   - 基于文本特征分析相似度
   - 识别学术短语、专业术语、统计数据
   - 区分原创内容和引用内容
   - 识别潜在来源类型（期刊、网络、学位论文等）
   - **只对问题特征计分**：过度使用学术短语、异常数字密度、引用密度过高等

2. **AIGC智能检测**
   - **从0%基准开始**：完全人工撰写的论文AIGC率为0%
   - 分析句式规整度和多样性
   - 检测AI常见表达模式
   - 评估内容深度和个性化程度
   - 提供风险等级和修改建议
   - **只对问题特征计分**：句式过于规整、使用AI常见表达、缺乏具体内容等

3. **剽窃类型智能识别**
   - 分析相似度等级判断剽窃类型
   - 检测文字表述、观点、整体剽窃
   - 识别过度引用行为

4. **相似内容检测**
   - 识别表格和公式引用重复
   - 检测潜在的格式化内容抄袭

5. **章节级别分析**
   - 自动识别论文章节结构
   - 按章节进行相似度统计
   - 识别高风险章节

## 检测方法论

### 核心原则

本检测工具遵循**0%基准原则**：
- ✅ **完全原创 = 0% 相似度**
- ✅ **完全人工撰写 = 0% AIGC率**
- ✅ **只对检测到的问题特征累积计分**
- ❌ **不预设基础分数**（避免有罪推定）

### 相似度检测方法

**计算公式**：
```
总文字复制比 = Σ(问题特征权重) / 总字数 × 100%

文字复制部分 = (重复字数 / 总字数) × 100%
无问题部分 = 100% - 文字复制部分
```

**检测特征及权重**：
- **过度使用学术套话**（>5个）：每超1个 +3%
  - 检测词：综上所述、因此、然而、首先、其次等
- **异常数字密度**（>10%）：+8%
  - 可能是复制数据导致
- **引用标记**：每个引用 +1.5%
  - 引用密度过高（>5个/100字）额外 +10%
- **过度密集的专业术语**（>4个）：每超1个 +2%
  - 检测词：数据、分析、方法、模型、算法等

**基于字数统计的指标**：
- **重复字数**：相似度≥30%的段落按比例累加的字数
- **文字复制部分**：重复字数占总字数的百分比
- **无问题部分**：原创内容占总字数的百分比（100% - 文字复制部分）
- **疑似段落数**：相似度≥30%的段落数量
- **单篇最大重复字数**：单个片段最大重复字数
- **前部重合字数**：前30%内容的重复字数
- **疑似段落最大/最小重合字数**：疑似段落的重合字数范围

### 维普指标计算方法

**三个核心指标**：
```
引用率 = (正确引用字数 / 总字数) × 100%
复写率 = (相似度≥50%的字数 / 总字数) × 100%
自写率 = (相似度<30%的字数 / 总字数) × 100%
```

**指标说明**：
- **引用率**：有引用标记（[ ]）的内容占比
- **复写率**：直接复制/高度相似内容（≥50%）的占比
- **自写率**：完全原创内容（<30%）的占比

**三者关系**：
- 引用率 + 复写率 + 自写率 ≈ 100%
- 正常论文：自写率应>50%，复写率<30%
- 优秀论文：自写率>70%，复写率<20%

### AIGC检测方法

**计算公式**：
```
AIGC总体生成率 = Σ(AI特征权重) / 总字数 × 100%
```

**检测特征及权重**：
- **句式过于规整**（方差<30）：+20%
- **句式较为规整**（方差30-50）：+10%
- **AI常见表达**：每个 +8%
  - 检测词：在当今社会、众所周知、总的来说等
- **缺乏具体内容**（>200字且无数据/例子）：+15%
- **过度使用情感色彩词**（>1个）：每超1个 +5%
  - 检测词：非常重要、十分关键、极其重要等

### 风险等级标准

**相似度风险等级**：
- 正常：<30%
- 低风险：30-40%
- 中风险：40-50%
- 高风险：50-60%
- 极高风险：≥60%

**AIGC风险等级**：
- 正常：<5%
- 低风险：5-15%
- 中风险：15-30%
- 高风险：30-50%
- 极高风险：≥50%

### 核心指标计算示例

**示例数据**：
```
总字数：41,593字
重复字数：369字
疑似段落数：8段
单篇最大重复字数：82字（第3章）
前部重合字数：125字
疑似段落最大重合字数：293字
疑似段落最小重合字数：76字
```

**计算结果**：
```
文字复制部分 = (369 / 41593) × 100% = 0.89%
无问题部分 = 100% - 0.89% = 99.11%
```

**解读**：
- 论文中有0.89%的内容被判定为相似/重复（369字）
- 99.11%的内容是原创的，无相似度问题
- 整体相似度很低，属于正常范围

### 方法二：手动分析流程

如果需要更细粒度的控制，可以手动调用各个分析步骤：

```python
import sys
sys.path.insert(0, '/skills/paper-detector/scripts')
from ai_paper_detector import AIPaperDetector

detector = AIPaperDetector()

# 1. 读取文档
doc_result = detector.read_document("论文.md")

# 2. 提取章节
sections = detector.extract_sections(content)

# 3. 分割文本
segments = detector.segment_text(content, sections)

# 4. 检测引用
citations, cleaned = detector.detect_citations(content)

# 5. 分析每个片段
for segment in segments:
    # 相似度分析
    sim_result = detector.analyze_similarity_with_ai(segment["content"])

    # AIGC检测
    aigc_result = detector.detect_aigc_with_ai(segment["content"])

    # 剽窃类型检测（新增）
    plagiarism_check = detector._detect_plagiarism_type(
        segment["content"],
        sim_result["similarity_score"]
    )

    # 过度引用检测（新增）
    is_over_citation = detector._detect_over_citation(
        segment["content"],
        citations
    )
```

### Step 3: 生成检测报告

使用 `generate_report.py` 生成报告：

```python
import sys
sys.path.insert(0, '/skills/paper-detector/scripts')
from generate_report import PaperDetectionReport

# 方法1: 从AI检测结果直接生成
result = detector.analyze_paper("论文.md")
paper_info = result["paper_info"]
detection_results = result["detection_results"]

# 生成报告
report = PaperDetectionReport(paper_info, detection_results)
simple_report = report.generate_simple_report()      # 简洁版
full_report = report.generate_full_report()          # 全文版
aigc_report = report.generate_aigc_report()          # AIGC专项报告

# 保存报告
report.save_report(simple_report, "简洁版报告.md")
report.save_report(full_report, "全文版报告.md")
report.save_report(aigc_report, "AIGC报告.md")
```

## 报告类型

### 简洁版报告

仅包含核心指标和统计数据：

- 基本信息（题目、作者、检测时间、编号）
- **检测结果汇总**（总字数、各项相似度、AIGC率、百分比划分）
- **字数统计**（8项详细字数指标）
- 相似度分布统计表
- **剽窃类型检测**（4种剽窃类型统计）

### 全文版报告

包含详细标注和完整分析：

- 简洁版的所有内容
- **字数统计详情**
- 相似片段详情列表（位置、相似度、字数、来源类型、内容摘要）
- **剽窃类型检测详情**：
  - 疑似剽窃观点详情（位置、描述、置信度）
  - 过度引用详情（位置、引用数量）
- **相似内容检测**：
  - 相似表格检测
  - 相似公式检测
- AIGC检测详细分析（高风险段落详情）

### AIGC专项报告

专注于AI内容检测：

- 基本信息
- AIGC检测结果汇总（总体生成率、风险等级）
- 各章节AIGC生成率统计表
- 高风险段落详情
- 修改建议

## 报告格式示例

```
# 论文检测报告（简洁版）

## 基本信息
- 论文题目：《[论文标题]》
- 作者：[作者姓名]
- 检测时间：2025年X月X日
- 检测编号：PD20250206123456789

## 检测结果汇总
- 原文总字数：XXXXX字

**知网指标**
- 总文字复制比：XX.X%
- 去除引用文献复制比：XX.X%
- 去除本人已发表文献复制比：XX.X%
- 单篇最大文字复制比：XX.X%

**维普指标**
- 引用率：XX.X%（正确引用内容占比）
- 复写率：XX.X%（相似度≥50%内容占比）
- 自写率：XX.X%（相似度<30%原创内容占比）

- AIGC总体生成率：XX.X%
- 文字复制部分：XX.X%（基于重复字数计算）
- 无问题部分：XX.X%（100% - 文字复制部分）

## 字数统计
- 总字数：XXXX
- 总段落数：XX
- 重复字数：XXX（相似度≥30%的段落按比例累加）
- 疑似段落数：XX（相似度≥30%的段落数）
- 单篇最大重复字数：XXX (章节名)
- 前部重合字数：XXX（前30%内容的重复字数）
- 疑似段落最大重合字数：XXX
- 疑似段落最小重合字数：XXX

> **说明**：
> - **文字复制部分** = (重复字数 / 总字数) × 100%
> - **无问题部分** = 100% - 文字复制部分
> - 这两个指标基于实际重复字数统计，更直观反映论文质量

## 相似度分布
| 相似度区间 | 段落数 | 字数 |
|-----------|--------|------|
| ≥50% | X | XXXX |
| 40%-50% | X | XXXX |
| 30%-40% | X | XXXX |
| <30% | X | XXXX |

## 剽窃类型检测
- 疑似剽窃观点：X 处
- 疑似剽窃文字表述：X 处
- 疑似整体剽窃：X 处
- 过度引用：X 处
```

## 注意事项

- 检测结果仅供参考，不代表最终学术评定
- 建议结合官方检测平台（知网、维普等）进行交叉验证
- 对于引用内容，应正确识别并标注
- 保持客观、专业的检测态度

## Resources

### scripts/

- **ai_paper_detector.py** - AI驱动的论文检测工具（推荐使用）
  - `AIPaperDetector` - 主检测器类
  - `analyze_paper()` - 完整分析论文并生成检测结果
  - `analyze_similarity_with_ai()` - AI相似度分析
  - `detect_aigc_with_ai()` - AI AIGC检测
  - `_detect_plagiarism_type()` - 剽窃类型检测（4种）
  - `_detect_over_citation()` - 过度引用检测
  - `_detect_similar_objects()` - 相似表格和公式检测
  - `read_document()` - 读取各种格式的论文文件
  - `extract_sections()` - 提取论文章节结构
  - `segment_text()` - 智能文本分段
  - `detect_citations()` - 引用识别

  **增强AI检测功能**（从ai文件夹整合）：
  - `EnhancedAIDetector` - 增强的AI检测器类
  - `detect_vocabulary_density()` - AI词汇密度检测
  - `detect_burstiness()` - 句式突发性检测
  - `detect_paraphrasing()` - 改写攻击检测
  - `comprehensive_detection()` - 综合AI检测

- **generate_report.py** - 报告生成工具
  - `PaperDetectionReport` - 报告生成器类
  - `generate_simple_report()` - 生成简洁版报告（包含所有新指标）
  - `generate_full_report()` - 生成全文版报告（包含详细分析）
  - `generate_aigc_report()` - 生成AIGC专项报告
  - `save_report()` - 保存报告到文件

### ai-references/

AI检测相关参考资料（从ai文件夹整合）：

- **advanced-detection.md** - 前沿AI检测技术
  - 改写攻击检测
  - 水印检测技术
  - 对抗攻击识别

- **chinese-resources.md** - 中文降AI率策略
  - 中文写作特点
  - 降AI率技巧
  - 常见问题解答

- **chapter-strategies.md** - 各章节降AI率策略
  - 摘要降AI率
  - 文献综述降AI率
  - 方法/结果/结论章节策略

- **detection-methods.md** - 详细检测方法
  - 词汇密度检测
  - 突发性分析
  - 改写痕迹识别

- **technical-principles.md** - 技术原理说明
  - 困惑度分析
  - 突发性理论
  - AI生成模式识别

- **tools-guide.md** - 检测工具完整指南
  - 工具对比
  - 使用方法
  - 结果解读

**注意**: `analyze_paper.py` 已被 `ai_paper_detector.py` 完全替代，不再建议使用。
