# AI检测脚本使用指南

本目录包含用于检测中文学术论文AI率的实用Python脚本。

## 📁 脚本列表

### 基础工具

| 脚本 | 功能 | 适用场景 |
|------|------|---------|
| `count_ai_words.py` | 统计AI词汇密度 | 快速筛查 |
| `check_abstract.py` | 摘要专项检测 | 摘要检查 |

### 高级工具

| 脚本 | 功能 | 适用场景 |
|------|------|---------|
| `detect_paraphrasing.py` | 改写攻击检测 | 可疑文本深度分析 |
| `comprehensive_detector.py` | 综合多维度检测 | 完整论文检测 |
| `batch_detector.py` | 批量处理 | 多文件/章节检测 |

## 🚀 快速开始

### 安装依赖

```bash
pip install jieba numpy
```

### 使用示例

#### 1. 快速词汇检测

```bash
# 检测单个文件
python count_ai_words.py thesis.txt

# 输出示例：
# AI词汇密度: 45.3个/1000字
# 风险等级: 中风险
```

#### 2. 摘要检测

```bash
python check_abstract.py abstract.txt
```

#### 3. 综合检测

```bash
python comprehensive_detector.py chapter.txt

# 输出完整的5维检测报告
```

#### 4. 改写攻击检测

```bash
python detect_paraphrasing.py suspicious_text.txt

# 检测是否经过改写工具处理
```

#### 5. 批量检测

```bash
# 检测多个文件
python batch_detector.py chapter1.txt chapter2.txt chapter3.txt

# 检测整个目录
python batch_detector.py thesis_chapters/

# 按章节自动检测
python batch_detector.py --chapters full_thesis.txt

# 输出JSON报告
python batch_detector.py thesis_chapters/ -o report.json
```

## 📊 检测指标说明

### AI词汇密度

- **<30个/1000字**: 安全 ✅
- **30-50个/1000字**: 注意 ⚠️
- **>50个/1000字**: 高风险 ❌

### 综合评分

- **<30%**: 安全 ✅
- **30-50%**: 低风险 ⚠️
- **50-70%**: 中风险 ⚠️⚠️
- **>70%**: 高风险 ❌

### 改写概率

- **<25%**: 未检测到改写 ✅
- **25-50%**: 轻微改写可能 ⚠️
- **50-75%**: 明显改写特征 ⚠️⚠️
- **>75%**: 高度疑似改写 ❌

## 🎯 使用建议

### 检测流程

```
1. 快速筛查
   └─ count_ai_words.py

2. 如果有问题，详细检测
   └─ comprehensive_detector.py

3. 按章节定位问题
   └─ batch_detector.py --chapters

4. 深度分析可疑章节
   └─ detect_paraphrasing.py
```

### 修改策略

根据检测结果，参考主文档（`../SKILL.md`）的修改建议：

- **高AI词汇** → 替换AI高频词
- **低突发性** → 调整句子长度变化
- **公式化** → 打破固定结构
- **改写痕迹** → 加入个人声音

## ⚠️ 重要提示

1. **工具仅供参考**: 不能完全替代人工审核
2. **结合学校标准**: 以学校指定的检测工具（知网）为准
3. **反复修改**: 一次修改通常不够
4. **保持学术诚信**: 工具是为了改进写作，不是规避检测

## 📖 相关文档

- **主要指南**: `../SKILL.md` - 完整的AI检测和降AI率策略
- **中文资源**: `../references/chinese-resources.md` - 详细的中文降AI率方法
- **英文研究**: `../references/english-research-resources.md` - 前沿研究技术

## 🔧 技术细节

### 检测原理

脚本基于以下原理：

1. **困惑度(Perplexity)**: AI文本过于可预测
2. **突发性(Burstiness)**: AI文本变化不够
3. **统计特征**: n-gram分布、词性序列
4. **模式识别**: 公式化表达、套话

### 算法来源

基于论文"Can AI-Generated Text be Reliably Detected?" (arXiv:2303.11156)
的研究成果，并针对中文学术写作场景进行适配。

### 改写攻击检测

参考研究中的Parrot和DIPPER改写器，识别：
- 词汇多样性异常
- 句子结构过于一致
- 缺乏个人声音
- 改写痕迹

## 💡 常见问题

**Q: 检测结果准确吗？**
A: 工具提供参考，但不是100%准确。建议结合多个工具和人工审核。

**Q: 如何降低AI率？**
A: 参考主文档的修改建议，关键是加入个人观点、使用具体数据、打破公式化结构。

**Q: 改写工具有用吗？**
A: 改写工具可能被检测。我们的`detect_paraphrasing.py`可以识别改写痕迹。

**Q: 摘要AI率特别高怎么办？**
A: 摘要是AI最高发区。不要"本文"开头，直接说发现，用具体数据。

**Q: 不同章节结果差异大？**
A: 正常。摘要、文献综述通常AI率较高，方法、结果部分相对较低。

## 📝 更新日志

- **2025-02**: 添加改写攻击检测
- **2025-02**: 整合多维度综合检测
- **2025-02**: 支持批量处理和章节检测
- **2025-01**: 初始版本

## 🤝 贡献

欢迎提出改进建议和问题反馈！

## 📄 许可

基于学术研究论文开发，仅供学习和研究使用。
