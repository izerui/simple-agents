---
name: 论文检测器
description: 专业的学术论文检测工具，能够生成类似知网、维普的专业查重和AIGC检测报告。当用户需要进行论文相似度检测、生成查重报告、检测论文中的AI生成内容（AIGC）、分析引用和相似片段，或创建专业检测报告时使用此技能。支持.md、.txt文件格式。强制工作流模式确保所有12个检测步骤和29个检测项都执行。
---

# 论文检测器 (Paper Detector)

**版本**: 2.0 (工作流版)
**最后更新**: 2025-02-07

专业的论文检测分析工具，能够对学术论文进行全面检测并生成类似知网、维普的专业查重和AIGC检测报告。

## 快速开始

### 一键检测（推荐）⭐

```bash
# 一键执行检测并生成所有报告（完全独立，单文件）
python3 /skills/paper-detector/scripts/one_click_detect_standalone.py paper.md
```

**输出文件**：
- `detection_result_*.json` - 检测结果（JSON格式）
- `reports/论文名_检测报告.md` - 检测报告

### Python API

```python
import sys
sys.path.insert(0, '/skills/paper-detector/scripts')
from one_click_detect_standalone import PaperDetector, ReportGenerator

# 创建检测器
detector = PaperDetector()

# 执行检测
result = detector.analyze_paper("paper.md")

# 生成报告
report_gen = ReportGenerator(
    result['paper_info'],
    result['detection_results']
)

# 生成检测报告
report = report_gen.generate_report()

# 保存报告
report_gen.save_report(report, "检测报告.md")
```

### 命令行参数

```bash
# 启用增强AI检测
python3 /skills/paper-detector/scripts/one_click_detect_standalone.py paper.md --enhanced-ai

# 指定输出目录
python3 /skills/paper-detector/scripts/one_click_detect_standalone.py paper.md --output-dir custom_reports
```

## 核心功能

### 1. 相似度检测（知网标准）

**核心指标（4项）**：
- 总文字复制比
- 去除引用文献复制比
- 去除本人已发表文献复制比
- 单篇最大文字复制比

**维普指标（3项）**：
- 引用率：正确引用内容占比
- 复写率：相似度≥50%内容占比
- 自写率：相似度<30%原创内容占比

**字数统计（8项）**：
- 总字数、总段落数、重复字数、疑似段落数
- 单篇最大重复字数及位置
- 前部重合字数
- 疑似段落最大/最小重合字数

**剽窃类型检测（4种）**：
- 观点剽窃（30-40%相似度）
- 文字表述剽窃（40-60%相似度）
- 整体剽窃（≥60%相似度，>300字）
- 过度引用（每100字超过3个引用）

### 2. AIGC检测

**基础检测（2项）**：
- AIGC总体生成率
- 各章节AIGC生成率

**增强AI检测（3项，可选）**：
- AI词汇密度（每1000字）
- 句式突发性（变异系数CV）
- 改写攻击检测

**风险等级**：
- 正常：<5%
- 低风险：5-15%
- 中风险：15-30%
- 高风险：30-50%
- 极高风险：≥50%

### 3. 相似内容检测

- 相似表格检测
- 相似公式检测

## 强制工作流

### 12个强制步骤

本技能使用**强制工作流模式**，确保所有检测步骤按顺序执行：

1. 文档读取与预处理
2. 章节提取
3. 文本分割
4. 引用识别
5. 相似度检测（核心）
6. AIGC检测（核心）
7. 剽窃类型检测（4种）
8. 过度引用检测
9. 相似内容检测（表格、公式）
10. 增强AI检测（3项）[可选]
11. 统计指标计算
12. 报告生成

### 29个核心检测项

**知网指标（4）**：总文字复制比、去除引用文献复制比、去除本人已发表文献复制比、单篇最大文字复制比

**维普指标（3）**：引用率、复写率、自写率

**字数统计（8）**：总字数、总段落数、重复字数、疑似段落数、单篇最大重复字数、单篇最大重复位置、前部重合字数、疑似段落最大/最小重合字数

**百分比划分（2）**：文字复制部分、无问题部分

**剽窃类型（4）**：疑似剽窃观点、疑似剽窃文字表述、疑似整体剽窃、过度引用

**相似内容（2）**：表格、公式

**AIGC检测（2）**：总体生成率、各章节生成率

**增强AI检测（3，可选）**：AI词汇密度、句式突发性、改写攻击

### 为什么使用强制工作流？

- ✅ **完整性**：所有步骤必须执行，不能跳过
- ✅ **覆盖性**：所有29个检测项都进行检查
- ✅ **可追溯性**：每个步骤都有完整的执行日志
- ✅ **错误处理**：任何步骤失败都会中断流程

## 使用场景

### 场景1：论文预检

提交论文前进行自查：

```python
result = detector.analyze_paper("thesis.md")

# 检查是否符合要求
similarity = float(result['detection_results']['total_similarity'].rstrip('%'))
aigc = float(result['detection_results']['aigc_rate'].rstrip('%'))

if similarity > 30:
    print("⚠️ 相似度过高！需要修改。")
if aigc > 10:
    print("⚠️ AIGC内容过高！需要修改。")
```

### 场景2：论文质量分析

多维度分析论文质量：

```python
# 分析剽窃类型
plagiarism = result['detection_results']['plagiarism_analysis']

print(f"观点剽窃: {len(plagiarism['suspected_idea_plagiarism'])} 处")
print(f"文字表述剽窃: {len(plagiarism['suspected_text_plagiarism'])} 处")
print(f"整体剽窃: {len(plagiarism['suspected_overall_plagiarism'])} 处")
print(f"过度引用: {plagiarism['over_citation_count']} 处")
```

### 场景3：增强AI分析

进行更深入的AI内容分析：

```python
result = detector.analyze_paper("paper.md", enhanced_ai=True)

# 访问增强AI结果
enhanced = result['detection_results']['enhanced_ai_results']

print(f"AI词汇密度: {enhanced['vocabulary']['density_per_1000']} 个/1000字")
print(f"句式突发性CV: {enhanced['burstiness']['cv']}")
print(f"改写攻击风险: {enhanced['paraphrasing']['risk_level']}")
print(f"综合风险: {enhanced['comprehensive']['overall_risk']}")
```

### 场景4：批量处理

批量处理多个论文文件：

```bash
# 使用脚本批量处理
for file in papers/*.md; do
    python3 scripts/one_click_detect_standalone.py "$file"
done
```

## 输出示例

### 控制台输出

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

### 检测结果结构

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
    }
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

## 参考标准

### 相似度阈值（知网）

| 等级 | 范围 | 颜色 | 操作 |
|------|------|------|------|
| 高相似度 | ≥50% | 红色 | 必须修改 |
| 中等相似度 | 40%-50% | 黄色 | 建议修改 |
| 低相似度 | 30%-40% | 绿色 | 注意调整 |
| 正常 | <30% | 无 | 无需处理 |

### AIGC风险等级

| 等级 | 生成率 | 风险 | 操作 |
|------|--------|------|------|
| 极高风险 | ≥50% | 很高 | 完全重写 |
| 高风险 | 30%-50% | 高 | 大幅修改 |
| 中风险 | 15%-30% | 中 | 重点修改 |
| 低风险 | 5%-15% | 低 | 适当修改 |
| 正常 | <5% | 无 | 无需处理 |

### 合格标准

- **本科毕业论文**：总文字复制比 ≤ 30%
- **硕士毕业论文**：总文字复制比 ≤ 20%
- **博士毕业论文**：总文字复制比 ≤ 15%
- **期刊投稿**：总文字复制比 ≤ 15%
- **AIGC生成率**：一般要求 ≤ 10%

## 限制说明

- **文件格式**：支持.md、.txt等纯文本格式
- **文件大小**：建议 < 10MB 以获得最佳性能
- **语言支持**：针对中文和英文优化
- **网络访问**：不需要（使用本地分析）
- **检测范围**：文本相似度和AIGC模式检测，非语义分析

## 常见问题

### 问题：误报率较高

**症状**：正常内容被标记为相似或AI生成

**解决方案**：
1. 确保引用使用[1]或(作者, 年份)格式标记
2. 增加个人观点和分析
3. 使用多样的句式结构
4. 包含具体的数据和案例

### 问题：工作流执行失败

**症状**：检测在某一步骤停止

**解决方案**：
```python
# 检查哪个步骤失败
workflow_info = result.get("workflow_info", {})
for step_result in workflow_info.get('steps_summary', []):
    if not step_result['success']:
        print(f"失败步骤: {step_result['step_name']}")
        print(f"错误: {step_result['error']}")

# 尝试使用传统模式（不推荐）
result = detector.analyze_paper("paper.md", use_workflow=False)
```

### 问题：处理速度慢

**症状**：大论文检测时间过长

**解决方案**：
1. 将大论文拆分为章节
2. 如不需要可禁用增强AI检测
3. 确保系统资源充足

## 测试验证

### 验证检测项

```python
# 验证所有核心检测项存在
required_items = [
    "total_similarity",
    "similarity_without_citations",
    "similarity_without_self",
    "max_single_similarity_ratio",
    "citation_rate",
    "copy_rate",
    "original_rate",
    "aigc_rate"
]

detection_results = result["detection_results"]

missing = [item for item in required_items if item not in detection_results]

if missing:
    print(f"❌ 缺少检测项: {missing}")
else:
    print("✅ 所有核心检测项都存在")
```

### 验证检测项

```python
# 验证所有核心检测项存在
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
    print(f"❌ 缺少检测项: {missing}")
else:
    print("✅ 所有核心检测项都存在")
```

## 高级主题

### 自定义工作流

```python
# 直接导入独立脚本中的类
import sys
sys.path.insert(0, '/skills/paper-detector/scripts')
from one_click_detect_standalone import PaperDetector

# 创建检测器
detector = PaperDetector()

# 执行检测
result = detector.analyze_paper("paper.md")
```

**参考文档**：
- `references/detection_workflow.md` - 工作流规范
- `references/detection_methods.md` - 检测方法原理

## 文档资源

### 核心文档

- **检测流程规范**：`references/detection_workflow.md` - 12个强制步骤详细说明 + 29个核心检测项清单
- **检测方法与原理**：`references/detection_methods.md` - 检测算法、判定标准、技术原理

### 进阶文档

- **前沿技术**：`references/advanced-detection.md` - 最新检测技术
- **章节策略**：`references/chapter-strategies.md` - 各章节检测策略
- **中文资源**：`references/chinese-resources.md` - 中文论文特点
- **工具指南**：`references/tools-guide.md` - 检测工具对比
- **系统架构**：已整合到 `detection_workflow.md`

## 版本历史

### v2.0 - 工作流版 (2025-02-07)

**新功能**：
- ✅ 强制工作流模式，12个强制步骤
- ✅ 完全覆盖29个核心检测项
- ✅ 增强AI检测（增加3项）
- ✅ 完整的步骤日志和错误处理
- ✅ 工作流测试套件

### v1.0 - 传统版

**功能**：
- 基础相似度和AIGC检测
- 剽窃类型检测
- 报告生成
- 保留向后兼容性

## 技术支持

如有问题、疑问或贡献意向：
- 查看 `references/` 目录中的文档
- 阅读 `references/detection_workflow.md` 了解详细工作流信息
- 阅读 `references/detection_methods.md` 了解检测方法原理
