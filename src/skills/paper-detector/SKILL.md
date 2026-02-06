---
name: Paper Detector
description: AI-powered academic paper detection tool that generates professional plagiarism and AIGC detection reports similar to CNKI and Weipu. Use when user needs to detect paper similarity or plagiarism, generate plagiarism detection reports, detect AI-generated content (AIGC) in papers, analyze citations and similar segments, or create professional detection reports. Supports .md, .txt, .docx, .pdf file formats. Enforced workflow mode ensures all 12 detection steps and 29 detection items are executed.
---

# Paper Detector

**Version**: 2.0 (Workflow Edition)
**Last Updated**: 2025-02-07

Professional academic paper detection tool that generates plagiarism and AIGC detection reports similar to CNKI and Weipu standards with mandatory workflow execution.

## Quick Start

### Basic Usage

```bash
# Navigate to skill directory
cd /skills/paper-detector

# Execute detection (all 12 steps run automatically)
python3 scripts/ai_paper_detector.py paper.md

# Generate formatted reports
python3 scripts/generate_report.py detection_result_*.json
```

### Enhanced Detection

```bash
# Enable enhanced AI detection (adds 3 detection items)
python3 scripts/ai_paper_detector.py paper.md --enhanced-ai
```

### Python API

```python
import sys
sys.path.insert(0, '/skills/paper-detector/scripts')
from ai_paper_detector import AIPaperDetector

# Create detector
detector = AIPaperDetector()

# Execute detection
result = detector.analyze_paper(
    "paper.md",
    use_workflow=True,      # Mandatory workflow (default)
    enhanced_ai=False       # Enhanced AI detection (optional)
)

# Access results
print(result['detection_results']['total_similarity'])
print(result['detection_results']['aigc_rate'])
```

## Features

### 1. Similarity Detection (CNKI Standard)

**Core Indicators (4 items)**:
- Total similarity ratio
- Similarity excluding citations
- Similarity excluding self-publications
- Max single-source similarity ratio

**Weipu Indicators (3 items)**:
- Citation rate: Properly cited content percentage
- Copy rate: Content with ≥50% similarity
- Original rate: Content with <30% similarity

**Word Count Statistics (8 items)**:
- Total words
- Total segments
- Duplicate words
- Suspected segment count
- Max single duplicate words + location
- Front overlap words
- Suspected segment max/min overlap words

**Plagiarism Type Detection (4 types)**:
- Idea plagiarism (30-40% similarity)
- Text expression plagiarism (40-60% similarity)
- Overall plagiarism (≥60% similarity, >300 words)
- Over-citation (>3 citations per 100 words)

### 2. AIGC Detection

**Basic Detection (2 items)**:
- Overall AIGC generation rate
- Chapter-wise AIGC generation rate

**Enhanced AI Detection (3 items, optional)**:
- AI vocabulary density (per 1000 words)
- Sentence burstiness (coefficient of variation CV)
- Paraphrasing attack detection

**Risk Levels**:
- Normal: <5%
- Low risk: 5-15%
- Medium risk: 15-30%
- High risk: 30-50%
- Extreme risk: ≥50%

### 3. Similar Content Detection

- Similar tables detection
- Similar formulas detection

## Mandatory Workflow

### 12 Enforced Steps

This skill uses a **mandatory workflow mode** that ensures all detection steps execute in sequence:

1. Document reading and preprocessing
2. Section extraction
3. Text segmentation
4. Citation detection
5. Similarity detection (core)
6. AIGC detection (core)
7. Plagiarism type detection (4 types)
8. Over-citation detection
9. Similar content detection (tables, formulas)
10. Enhanced AI detection (3 items) [optional]
11. Metrics calculation
12. Report generation

### 29 Core Detection Items

**CNKI indicators (4)**: Total similarity, similarity without citations, similarity without self, max single similarity

**Weipu indicators (3)**: Citation rate, copy rate, original rate

**Word count (8)**: Total words, segments, duplicate words, suspected segments, max duplicate, location, front overlap, min/max overlap

**Percentage (2)**: Copy part percentage, problem-free percentage

**Plagiarism types (4)**: Idea, text expression, overall, over-citation

**Similar content (2)**: Tables, formulas

**AIGC (2)**: Overall rate, chapter rates

**Enhanced AI (3, optional)**: Vocabulary density, burstiness, paraphrasing

### Why Mandatory Workflow?

- ✅ **Completeness**: All steps must execute, no skipping
- ✅ **Coverage**: All 29 detection items are checked
- ✅ **Traceability**: Complete execution logs for each step
- ✅ **Error Handling**: Any step failure interrupts the flow

## Use Cases

### Case 1: Thesis Pre-Check

Before submitting your thesis, check for plagiarism and AIGC content:

```python
result = detector.analyze_paper("thesis.md")

# Check if meets requirements
similarity = float(result['detection_results']['total_similarity'].rstrip('%'))
aigc = float(result['detection_results']['aigc_rate'].rstrip('%'))

if similarity > 30:
    print("⚠️ Similarity too high! Needs revision.")
if aigc > 10:
    print("⚠️ AIGC content too high! Needs revision.")
```

### Case 2: Paper Quality Analysis

Analyze paper quality across multiple dimensions:

```python
# Analyze plagiarism types
plagiarism = result['detection_results']['plagiarism_analysis']

print(f"Idea plagiarism: {len(plagiarism['suspected_idea_plagiarism'])} cases")
print(f"Text plagiarism: {len(plagiarism['suspected_text_plagiarism'])} cases")
print(f"Overall plagiarism: {len(plagiarism['suspected_overall_plagiarism'])} cases")
print(f"Over-citation: {plagiarism['over_citation_count']} cases")
```

### Case 3: Enhanced AI Analysis

For deeper AI content analysis:

```python
result = detector.analyze_paper("paper.md", enhanced_ai=True)

# Access enhanced AI results
enhanced = result['detection_results']['enhanced_ai_results']

print(f"Vocabulary density: {enhanced['vocabulary']['density_per_1000']}/1000 words")
print(f"Burstiness CV: {enhanced['burstiness']['cv']}")
print(f"Paraphrasing risk: {enhanced['paraphrasing']['risk_level']}")
print(f"Overall risk: {enhanced['comprehensive']['overall_risk']}")
```

### Case 4: Report Generation

Generate professional detection reports:

```python
from generate_report import PaperDetectionReport

# Create report generator
report_gen = PaperDetectionReport(
    result['paper_info'],
    result['detection_results']
)

# Generate 3 types of reports
simple_report = report_gen.generate_simple_report()
full_report = report_gen.generate_full_report()
aigc_report = report_gen.generate_aigc_report()

# Save reports
report_gen.save_report(simple_report, "simple_report.md")
report_gen.save_report(full_report, "full_report.md")
report_gen.save_report(aigc_report, "aigc_report.md")
```

## Output Examples

### Console Output

```
======================================================================
🔍 论文检测流程启动
======================================================================
⚠️  强制模式：将执行所有 12 个检测步骤
📁 文件路径: paper.md
🤖 增强AI检测: 关闭

📍 步骤 1/12: 文档读取与预处理
----------------------------------------------------------------------
  📖 读取文档内容...
  ✅ 成功读取文档
     - 字数: 41593
     - 段落数: 156

...

======================================================================
✅ 检测流程全部完成
======================================================================

论文信息:
  题目: 未知
  作者: 未知
  字数: 41593

检测结果:
  总文字复制比: 5.2%
  去除引用文献复制比: 4.8%
  去除本人已发表文献复制比: 5.2%
  单篇最大文字复制比: 1.2%
  AIGC总体生成率: 8.5%
```

### Detection Result Structure

```json
{
  "paper_info": {
    "title": "论文标题",
    "author": "作者",
    "word_count": 41593,
    "paragraph_count": 156
  },
  "detection_results": {
    "total_similarity": "5.2%",
    "similarity_without_citations": "4.8%",
    "similarity_without_self": "5.2%",
    "max_single_similarity_ratio": "1.2%",
    "citation_rate": "12.5%",
    "copy_rate": "3.8%",
    "original_rate": "83.7%",
    "total_words": 41593,
    "duplicate_words": 2163,
    "suspected_segment_count": 8,
    "aigc_rate": "8.5%",
    "distribution": {
      "≥50%": {"count": 0, "words": 0},
      "40%-50%": {"count": 1, "words": 150},
      "30%-40%": {"count": 2, "words": 280},
      "<30%": {"count": 153, "words": 41163}
    },
    "similar_segments": [...],
    "plagiarism_analysis": {
      "suspected_idea_plagiarism": [...],
      "suspected_text_plagiarism": [...],
      "suspected_overall_plagiarism": [...],
      "over_citation_segments": [...]
    },
    "similar_objects": {...},
    "aigc_analysis": {...}
  },
  "metadata": {
    "detection_id": "PD20250207123456789",
    "detection_time": "2025-02-07 14:30:25",
    "workflow_mode": "enabled",
    "workflow_steps_completed": 12,
    "workflow_success_rate": "100.0%"
  }
}
```

## Reference Standards

### Similarity Thresholds (CNKI)

| Level | Range | Color | Action |
|-------|-------|-------|--------|
| High | ≥50% | Red | Must revise |
| Medium | 40%-50% | Yellow | Should revise |
| Low | 30%-40% | Green | Consider revising |
| Normal | <30% | None | No action needed |

### AIGC Risk Levels

| Level | Rate | Risk | Action |
|-------|------|------|--------|
| Extreme | ≥50% | Very High | Complete rewrite |
| High | 30%-50% | High | Major revision |
| Medium | 15%-30% | Medium | Focused revision |
| Low | 5%-15% | Low | Minor revision |
| Normal | <5% | None | No action needed |

### Acceptance Standards

- **Bachelor thesis**: Total similarity ≤ 30%
- **Master thesis**: Total similarity ≤ 20%
- **PhD thesis**: Total similarity ≤ 15%
- **Journal submission**: Total similarity ≤ 15%
- **AIGC rate**: Generally ≤ 10%

## Limitations

- **File formats**: Supports .md, .txt, .docx, .pdf (must be readable as text)
- **File size**: Recommended < 10MB for optimal performance
- **Language**: Optimized for Chinese and English
- **Network access**: Not required (uses local analysis)
- **Detection scope**: Text similarity and AIGC patterns, not semantic analysis

## Common Issues

### Issue: High false positive rate

**Symptoms**: Normal content flagged as similar or AI-generated

**Solutions**:
1. Ensure proper citations are marked with [1] or (Author, Year)
2. Add personal insights and analysis
3. Use varied sentence structures
4. Include specific data and examples

### Issue: Workflow execution fails

**Symptoms**: Detection stops at a certain step

**Solutions**:
```python
# Check which step failed
workflow_info = result.get("workflow_info", {})
for step_result in workflow_info.get('steps_summary', []):
    if not step_result['success']:
        print(f"Failed step: {step_result['step_name']}")
        print(f"Error: {step_result['error']}")

# Try using traditional mode (not recommended)
result = detector.analyze_paper("paper.md", use_workflow=False)
```

### Issue: Processing too slow

**Symptoms**: Detection takes too long for large papers

**Solutions**:
1. Split large papers into chapters
2. Disable enhanced AI detection if not needed
3. Ensure sufficient system resources

## Testing

### Test Workflow

```bash
# Run workflow tests
python3 scripts/test_workflow.py
```

Expected output:
```
✅ 步骤覆盖测试: All steps implemented
✅ 检测项覆盖测试: 29 core items documented
✅ 工作流检测测试: Workflow execution successful
```

### Verify Detection Items

```python
# Verify all core detection items exist
required_items = [
    "total_similarity",
    "similarity_without_citations",
    "citation_rate",
    "copy_rate",
    "original_rate",
    "total_words",
    "duplicate_words",
    "aigc_rate"
]

detection_results = result["detection_results"]

missing = [item for item in required_items if item not in detection_results]

if missing:
    print(f"❌ Missing items: {missing}")
else:
    print("✅ All core detection items present")
```

## Advanced Topics

### Custom Workflow

Create custom detection workflows:

```python
from detection_workflow import DetectionWorkflow, DetectionStep

class CustomWorkflow(DetectionWorkflow):
    # Add custom steps
    pass
```

See `references/detection_workflow.md` for details.

### Report Templates

Customize report templates in `assets/report_template.md`

### Integration with Other Tools

```python
# Integrate with document processing
from docx import Document

doc = Document("paper.docx")
text = "\n".join([para.text for para in doc.paragraphs])

# Save as temp file
with open("temp.md", "w") as f:
    f.write(text)

# Detect
result = detector.analyze_paper("temp.md")
```

## Documentation

- **Workflow specification**: `references/detection_workflow.md`
- **Quick start guide**: `references/quick_start_workflow.md`
- **Detection checklist**: `references/detection_items_checklist.md`
- **System architecture**: `detection_flow_architecture.md`

## Version History

### v2.0 - Workflow Edition (2025-02-07)

**New Features**:
- ✅ Mandatory workflow mode with 12 enforced steps
- ✅ Complete coverage of 29 core detection items
- ✅ Enhanced AI detection (3 additional items)
- ✅ Comprehensive step logging and error handling
- ✅ Workflow testing suite

### v1.0 - Traditional Edition

**Features**:
- Basic similarity and AIGC detection
- Plagiarism type detection
- Report generation
- Maintained for backward compatibility

## Support

For issues, questions, or contributions:
- Check documentation in `references/` directory
- Review `references/detection_workflow.md` for detailed workflow info
- Run `python3 scripts/test_workflow.py` for diagnostics

---

**Related Skills**:
- `document-skills:docx` - For working with .docx files
- `document-skills:pdf` - For working with PDF files

**See Also**:
- [Claude Skills Best Practices](https://claudecn.com/docs/agent-skills/best-practices/)
- [Agent Skills Documentation](https://claudecn.com/docs/agent-skills/)
