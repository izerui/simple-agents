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
python3 /skills/paper-detector/scripts/ai_paper_detector.py /path/to/paper.md

# 2. 生成检测报告
python3 /skills/paper-detector/scripts/generate_report.py detection_result_PDXXXXXXXXXXXX.json
```

**注意**: `ai_paper_detector.py` 是新版本的AI驱动检测工具，能够真正分析论文内容并计算相似度和AIGC生成率。

## 核心功能

### 1. 论文相似度检测

分析论文与已有文献的相似程度，识别潜在的重复或高度相似内容。

**检测指标**：
- **总文字复制比** - 整体相似度百分比
- **去除引用文献复制比** - 排除引用后的相似度
- **去除本人已发表文献复制比** - 排除本人已发表作品的相似度

**相似度等级划分**：
- 高相似度（≥50%）- 红色标注
- 中等相似度（40%-50%）- 黄色标注
- 低相似度（30%-40%）- 绿色标注

### 2. AIGC检测

检测论文中AI生成内容的比例，识别高风险AI生成段落。

**检测内容**：
- AIGC总体生成率
- 各章节/段落的AIGC生成率
- 高风险段落标注
- 风险等级评定

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
#   * total_similarity: 总文字复制比
#   * similarity_without_citations: 去除引用文献复制比
#   * aigc_rate: AIGC总体生成率
#   * distribution: 相似度分布统计
#   * similar_segments: 相似片段详情列表
#   * aigc_analysis: AIGC检测详细分析
# - metadata: 检测元数据
```

**AI检测特点**：

1. **智能相似度分析**
   - 基于文本特征分析相似度
   - 识别学术短语、专业术语、统计数据
   - 区分原创内容和引用内容
   - 识别潜在来源类型（期刊、网络、学位论文等）

2. **AIGC智能检测**
   - 分析句式规整度和多样性
   - 检测AI常见表达模式
   - 评估内容深度和个性化程度
   - 提供风险等级和修改建议

3. **章节级别分析**
   - 自动识别论文章节结构
   - 按章节进行相似度统计
   - 识别高风险章节

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
- 检测结果汇总（总字数、各项相似度、AIGC率）
- 相似度分布统计表

### 全文版报告

包含详细标注和完整分析：

- 简洁版的所有内容
- 相似片段详情列表（位置、相似度、字数、来源类型、内容摘要）
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
# 论文检测报告

## 基本信息
- 论文题目：《[论文标题]》
- 作者：[作者姓名]
- 检测时间：2025年X月X日
- 检测编号：PD20250206123456789

## 检测结果汇总
- 原文总字数：XXXXX字
- 总文字复制比：XX.X%
- 去除引用文献复制比：XX.X%
- 去除本人已发表文献复制比：XX.X%
- AIGC总体生成率：XX.X%

## 相似度分布
| 相似度区间 | 段落数 | 字数 |
|-----------|--------|------|
| ≥50% | X | XXXX |
| 40%-50% | X | XXXX |
| 30%-40% | X | XXXX |
| <30% | X | XXXX |

## 相似片段详情
[详细列出各相似片段...]

## AIGC检测分析
[详细的AIGC检测结果...]
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
  - `read_document()` - 读取各种格式的论文文件
  - `extract_sections()` - 提取论文章节结构
  - `segment_text()` - 智能文本分段
  - `detect_citations()` - 引用识别

- **analyze_paper.py** - 基础论文内容提取工具
  - `read_document()` - 读取各种格式的论文文件
  - `extract_sections()` - 提取论文章节结构
  - `segment_text()` - 文本分段处理
  - `detect_citations()` - 引用识别

- **generate_report.py** - 报告生成工具
  - `PaperDetectionReport` - 报告生成器类
  - `generate_simple_report()` - 生成简洁版报告
  - `generate_full_report()` - 生成全文版报告
  - `generate_aigc_report()` - 生成AIGC专项报告
  - `save_report()` - 保存报告到文件
