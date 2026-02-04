# English Research Resources for AI Text Detection

> Based on research from the paper "Can AI-Generated Text be Reliably Detected?" (arXiv:2303.11156)
> 
> This document provides advanced insights into paraphrasing attacks, watermark detection, and adversarial techniques.

## Table of Contents

1. [Core Research Paper](#core-research-paper)
2. [Paraphrasing Attacks](#paraphrasing-attacks)
3. [Watermark Detection](#watermark-detection)
4. [Impossibility Results](#impossibility-results)
5. [Adversarial Attacks](#adversarial-attacks)
6. [Evaluation Metrics](#evaluation-metrics)
7. [Tools and Models](#tools-and-models)
8. [Code References](#code-references)

---

## Core Research Paper

**Title**: Can AI-Generated Text be Reliably Detected?

**Authors**: University of Maryland researchers

**Paper Link**: https://arxiv.org/abs/2303.11156

**GitHub Repository**: https://github.com/vinusankars/Reliability-of-AI-text-detectors

**Key Findings**:
- Paraphrasing attacks can effectively bypass AI detectors
- Watermarking methods are vulnerable to paraphrasing
- There are theoretical limitations to reliable detection
- Adversarial attacks can fool detectors

---

## Paraphrasing Attacks

### Overview

Paraphrasing attacks modify AI-generated text to evade detection while preserving meaning. The research demonstrates that paraphrasing can significantly reduce detection rates.

### Types of Paraphrasing

#### 1. **Single-round Paraphrasing**

Using models like Parrot Paraphraser to rephrase text once.

**Model**: `prithivida/parrot_paraphraser_on_T5` (based on T5)

**Parameters**:
- `diversity_ranker`: "levenshtein"
- `adequacy_threshold`: 0.6-0.9
- `fluency_threshold`: 0.6-0.9
- `max_return_phrases`: 10
- `max_length`: 200

**Impact on Detection**:
- Original: 98% detection rate
- After paraphrasing: 57% detection rate

#### 2. **Recursive Paraphrasing**

Using DIPPER paraphraser for multiple rounds of paraphrasing.

**Model**: `kalpeshk2011/dipper-paraphraser-xxl` (T5-XXL based)

**Parameters**:
- `lex_diversity`: 0-100 (multiples of 20)
- `order_diversity`: 0-100 (multiples of 20)
- `lex_code`: 100 - lex_diversity
- `order_code`: 100 - order_diversity

**Example**:
```python
# Input: Watermarked text
# After 5 rounds of paraphrasing
# Result: Detection rate drops significantly
```

### Paraphrasing Strategies

**Lexical Diversity**:
- 0: No diversity, preserve exact words
- 20-60: Moderate lexical changes
- 80-100: Maximum lexical diversity

**Order Diversity**:
- 0: Preserve sentence order
- 20-60: Moderate reordering
- 60-100: Significant reordering

### Detection Evasion Results

| Text Type | Tokens | Green Tokens | Detection Rate |
|-----------|--------|--------------|----------------|
| Watermarked | 17,478 | 10,085 | 98% |
| Single Paraphrase | 14,147 | 5,681 | 57% |
| Multi-round Paraphrase | - | - | <20% |

---

## Watermark Detection

### Watermarking Concept

Watermarking embeds a detectable signal in AI-generated text by biasing token selection.

### Key Components

#### 1. **Greenlist Tokens**

At each generation step, a fraction of vocabulary is designated as "greenlist" tokens.

**Gamma (γ)**: Fraction of vocabulary in greenlist (typically 0.25)

**Delta (δ)**: Bias added to greenlist token logits (typically 2.0)

#### 2. **Seeding Schemes**

**Simple_1**: Basic seeding scheme
**Other schemes**: More advanced permutations available

### Detection Metrics

#### 1. **Z-Score Detection**

```python
z_score = (green_count - expected_green) / std_dev
```

**Threshold**: Typically 4.0 (above threshold = watermarked)

#### 2. **P-Value**

Statistical significance of the watermark signal.

#### 3. **Green Token Fraction**

Percentage of tokens in the text that are in the greenlist.

**Formula**:
```
green_fraction = green_tokens / total_tokens
```

### Watermark Detection Implementation

**Key Functions**:
- `WatermarkLogitsProcessor`: Applies watermark during generation
- `WatermarkDetector`: Detects watermarks in text

**Detection Parameters**:
```python
vocab = list(tokenizer.get_vocab().values())
gamma = 0.25          # Fraction of vocabulary in greenlist
delta = 2.0           # Bias for greenlist tokens
seeding_scheme = "simple_1"
z_threshold = 4.0     # Detection threshold
```

### Watermarking Libraries

**Primary Library**: https://github.com/jwkirchenbauer/lm-watermarking

**Integration**: The research repository integrates this library for watermarking experiments.

---

## Impossibility Results

### Theoretical Limitations

Research shows fundamental limitations in AI text detection reliability.

### Total Variation (TV) Analysis

#### 1. **What is Total Variation?**

TV measures the distributional difference between human-written and AI-generated text.

**Formula**:
```
TV(P, Q) = 0.5 * Σ |P(x) - Q(x)|
```

Where:
- P: Human text distribution
- Q: AI text distribution
- x: Token sequences

#### 2. **TV Estimation Using RoBERTa**

**Model**: `roberta-large`

**Training**:
```bash
python roberta_tv.py [human-dataset] [ai-dataset] \
    --data_dir [path] \
    --tv_model roberta-large \
    --batch_size 20 \
    --seq_len 50
```

**Evaluation**:
```bash
python eval_tv.py [human-dataset] \
    --model_name roberta-large \
    --data_dir [path]
```

#### 3. **TV Values for Different Models**

| Model | TV Distance | Detection Difficulty |
|-------|-------------|---------------------|
| GPT-2 117M | Low | Easy |
| GPT-2 XL | Medium | Moderate |
| GPT-3 | High | Difficult |

### AUROC Bound Analysis

**Theoretical Bound**: ROC AUC is bounded by TV distance.

**Formula**:
```
AUC ≤ 0.5 + 0.5 * TV
```

**Implication**: 
- If TV is small, maximum achievable AUC is limited
- This explains why detectors struggle with advanced AI models

### Performance vs Overlap

Research shows detector performance correlates with:
- Training data overlap
- Model size
- Training similarity

---

## Adversarial Attacks

### Spoofing Attacks

#### 1. **Pair Distribution Attacks**

Generates text that mimics the distribution of detected text to fool classifiers.

**Key Files**:
- `pair-distribution/get_matrix.py`
- `pair-distribution/manual_generation.py`
- `pair-distribution/utils.py`

#### 2. **Attack Strategies**

**Token-level manipulation**: Modify specific tokens to change detection scores

**Distribution matching**: Generate text that matches expected distribution

**Gradient-based attacks**: Use gradients to find minimal perturbations

### Attack Effectiveness

**Original Detection Rate**: 80-95%
**After Adversarial Attack**: Can be reduced to 20-40%

### Defense Strategies

1. **Ensemble Detection**: Use multiple detectors
2. **Adversarial Training**: Train on adversarial examples
3. **Distribution Monitoring**: Detect anomalous distributions

---

## Evaluation Metrics

### Primary Metrics

#### 1. **Detection Accuracy**

**Accuracy**: (TP + TN) / (TP + TN + FP + FN)

#### 2. **ROC AUC**

Area under ROC curve - measures separability between human and AI text.

**Formula**:
```
AUC = P(score_human > score_ai)
```

#### 3. **False Positive Rate (FPR)**

```
FPR = FP / (FP + TN)
```

**Importance**: Critical for academic applications (avoid false accusations)

#### 4. **False Negative Rate (FNR)**

```
FNR = FN / (FN + TP)
```

**Importance**: Important for content moderation

### TV Calculation

**TV as Detection Metric**:

```python
def calculate_tv(scores, labels, threshold):
    tp, fp, tn, fn = 0, 0, 0, 0
    
    for i in range(len(scores)):
        if scores[i] >= threshold:
            if labels[i] == 1:
                tp += 1
            else:
                fp += 1
        else:
            if labels[i] == 1:
                fn += 1
            else:
                tn += 1
    
    tpr = tp / (tp + fn)  # True Positive Rate
    fpr = fp / (fp + tn)  # False Positive Rate
    
    return tpr - fpr  # Total Variation
```

---

## Tools and Models

### Paraphrasing Tools

#### 1. **Parrot Paraphraser**

**Model**: `prithivida/parrot_paraphraser_on_T5`

**Usage**:
```python
from parrot import Parrot

parrot = Parrot(model_tag="prithivida/parrot_paraphraser_on_T5", use_gpu=True)
para_phrases = parrot.augment(
    input_phrase=phrase,
    diversity_ranker="levenshtein",
    do_diverse=False,
    max_return_phrases=10,
    max_length=200,
    adequacy_threshold=0.9,
    fluency_threshold=0.9,
    use_gpu=True
)
```

#### 2. **DIPPER Paraphraser**

**Model**: `kalpeshk2011/dipper-paraphraser-xxl`

**Reference**: https://github.com/martiansideofthemoon/ai-detection-paraphrases

**Usage**:
```python
class DipperParaphraser:
    def paraphrase(self, input_text, lex_diversity, order_diversity, 
                   prefix="", sent_interval=3, **kwargs):
        # Paraphrase using DIPPER
        pass
```

### Watermarking Tools

**Library**: https://github.com/jwkirchenbauer/lm-watermarking

**Components**:
- `WatermarkLogitsProcessor`: Apply watermark during generation
- `WatermarkDetector`: Detect watermarks in text

### Detection Models

#### 1. **RoBERTa-based Detectors**

**Model**: `roberta-large`

**Training**:
```python
# Train TV estimation model
python roberta_tv.py [human-dataset] [ai-dataset] \
    --data_dir [path] \
    --tv_model roberta-large \
    --batch_size 20 \
    --seq_len 50
```

#### 2. **GPT-2 Models**

Used for generating AI text in experiments:
- `gpt2-small` (117M)
- `gpt2-medium` (345M)
- `gpt2-large` (762M)
- `gpt2-xl` (1.5B)

---

## Code References

### Complete Code Structure

The reference implementation (`docs/derector/`) contains three main research directories:

#### 1. `rephrase/` - Paraphrasing Attack Research

**Purpose**: Study how paraphrasing attacks affect AI detection

**Key Files**:
- `detect.py` - Watermark detection and Parrot paraphrasing
- `recursive_paraphrase.py` - Multi-round DIPPER paraphrasing
- `rephraser.py` - Parrot paraphraser implementation
- `eval.py` - Evaluation metrics for paraphrasing effectiveness
- `gather_sentences.py` - Sentence collection tools
- `utils.py` - Shared utility functions
- `pegasus/` - Pegasus-based paraphrasing tools

**Research Findings**:
- Detection rate drops from 98% → 57% after single paraphrase
- Recursive paraphrasing can reduce detection to <20%
- Paraphrasing significantly disrupts watermark signals

#### 2. `impossibility/` - Theoretical Limitations

**Purpose**: Investigate theoretical bounds on AI detection reliability

**Key Files**:
- `roberta_tv.py` - Train RoBERTa to estimate Total Variation (TV)
- `eval_tv.py` - Evaluate TV on validation datasets
- `plot_tv.py` - Visualize TV estimates
- `roc_bound.py` - Calculate and plot ROC AUC bounds
- `performance_vs_overlap.py` - Analyze performance vs training overlap
- `tv_from_density.py` - Calculate TV from density estimation
- `tools.py` - Utility functions for TV calculation

**Key Formulas**:
```
TV(P, Q) = 0.5 × Σ |P(x) - Q(x)|
AUC ≤ 0.5 + 0.5 × TV
```

**Research Findings**:
- TV bounds maximum achievable detection accuracy
- Larger models (GPT-3) have smaller TV → harder to detect
- Theoretical limit explains detector failures

#### 3. `pair-distribution/` - Adversarial Attacks

**Purpose**: Develop and test adversarial attack strategies

**Key Files**:
- `get_matrix.py` - Generate detection confusion matrix
- `manual_generation.py` - Manually generate adversarial examples
- `plot.py` - Visualize attack results
- `utils.py` - Attack utility functions
- `wordlist.py` - Word list for generating attacks
- `images/` - Visualization outputs

**Attack Strategy**:
1. Analyze detector's decision boundary
2. Generate text matching "human-like" distribution
3. Use minimal modifications to fool detector
4. Achieve significant detection rate reduction

### Key Scripts and Their Functions

#### Rephrase Directory

**`rephrase/detect.py`**: Paraphrasing attack using Parrot
```python
# Detects watermarked text and applies paraphrasing
# Uses Parrot paraphraser
# Saves rephrased results
```

**`rephrase/recursive_paraphrase.py`**: Recursive paraphrasing using DIPPER
```python
# Applies multiple rounds of paraphrasing
# Uses DIPPER paraphraser
# Configurable lexical and order diversity
```

**`rephrase/eval.py`**: Evaluates detection on rephrased text
```python
# Evaluates watermarked text statistics
# Evaluates rephrased text statistics
# Reports detection accuracy
```

**`rephrase/utils.py`**: Utility functions for rephrase experiments
```python
# Model loading
# Text generation
# Watermark detection
# Argument parsing
```

#### Impossibility Directory

**`impossibility/roberta_tv.py`**: TV estimation using RoBERTa
```python
# Trains RoBERTa to estimate TV
# Evaluates TV between datasets
```

**`impossibility/eval_tv.py`**: TV evaluation
```python
# Evaluates TV using trained model
# Saves TV estimates to JSON
```

**`impossibility/plot_tv.py`**: TV visualization
```python
# Plots TV estimates
# Creates visual comparisons
```

**`impossibility/roc_bound.py`**: ROC bound calculation
```python
# Calculates theoretical ROC bounds
# Plots bound curves
```

#### Pair-distribution Directory

**`pair-distribution/get_matrix.py`**: Gets confusion matrix
```python
# Calculates detection confusion matrix
# Analyzes detection performance
```

**`pair-distribution/manual_generation.py`**: Manual adversarial generation
```python
# Generates adversarial examples
# Tests attack effectiveness
```

### Dataset Support

**Supported Datasets**:
```python
DATASETS = [
    'webtext',              # Human-generated text
    'small-117M',           # GPT-2 generated
    'small-117M-k40',
    'medium-345M',
    'medium-345M-k40',
    'large-762M',
    'large-762M-k40',
    'xl-1542M',
    'xl-1542M-k40'
]
```

---

## Research Insights and Practical Applications

### Key Takeaways for AI Detection

1. **Paraphrasing is Effective**: Even simple paraphrasing can reduce detection rates by 40-50%

2. **Watermarking is Vulnerable**: Watermarked text can be paraphrased to remove the watermark signal

3. **Theoretical Limits Exist**: TV distance bounds maximum achievable detection accuracy

4. **Adversarial Attacks Work**: Sophisticated attacks can fool most detectors

5. **Model Size Matters**: Larger models produce text closer to human distribution

### Recommendations for Detection

1. **Use Ensemble Methods**: Combine multiple detection approaches

2. **Monitor for Paraphrasing**: Look for signs of paraphrasing attacks

3. **Consider Watermarking**: But understand its limitations

4. **Set Conservative Thresholds**: Balance false positives vs false negatives

5. **Continuous Updates**: Regularly update detectors as AI improves

### For Academic Writing

1. **Avoid Pure AI Generation**: Human editing is essential

2. **Be Cautious with Paraphrasing**: Paraphrased AI text may still be detectable

3. **Understand Limitations**: No detector is 100% accurate

4. **Use Multiple Tools**: Cross-validate with different detectors

5. **Focus on Quality**: High-quality writing naturally resists detection

---

## Further Reading

### Papers

1. **Can AI-Generated Text be Reliably Detected?**
   - https://arxiv.org/abs/2303.11156

2. **A Watermark for Large Language Models**
   - Kirchenbauer et al., 2023

3. **DIPPER: Diverse Paraphrasing via Prompting and Rewriting**
   - Krishna et al., 2023

### Tools and Libraries

1. **lm-watermarking**: https://github.com/jwkirchenbauer/lm-watermarking
2. **ai-detection-paraphrases**: https://github.com/martiansideofthemoon/ai-detection-paraphrases
3. **Parrot Paraphraser**: https://github.com/PrithivirajDamodaran/Parrot_Paraphraser

### Code Repositories

1. **Reliability of AI Text Detectors**: https://github.com/vinusankars/Reliability-of-AI-text-detectors
2. **LM Watermarking**: https://github.com/jwkirchenbauer/lm-watermarking
3. **AI Detection Paraphrases**: https://github.com/martiansideofthemoon/ai-detection-paraphrases

---

## Citation

If you use this research, please cite:

```
@article{reliability2023,
  title={Can AI-Generated Text be Reliably Detected?},
  author={University of Maryland researchers},
  journal={arXiv preprint arXiv:2303.11156},
  year={2023}
}
```

---

**Note**: This document summarizes research findings from the academic paper and associated code repository. For the most up-to-date information, please refer to the original sources.

---

## Practical Chinese Detection Implementation

### Adapting English Research to Chinese

While the reference research focuses on English text, the principles apply to Chinese with modifications:

#### 1. Tokenization Differences

**English**: Space-separated tokens
```python
words = text.split()
```

**Chinese**: Requires word segmentation
```python
import jieba
words = list(jieba.cut(text))
```

#### 2. Vocabulary Adaptation

**English AI vocabulary**:
- "Furthermore", "Moreover", "Additionally"
- "Significant", "Crucial", "Important"
- "Demonstrate", "Indicate", "Suggest"

**Chinese AI vocabulary** (see `chinese-resources.md`):
- 连接词：此外、同时、另外、再者
- 形容词：重要的、关键的、核心的
- 动词：体现、反映、表明、展现

#### 3. Sentence Structure Analysis

**English**: Word count, punctuation patterns
```python
sentence_length = len(words)
```

**Chinese**: Character count, unique segmentation patterns
```python
sentence_length = len(sentence)  # Characters
# Or use words after jieba segmentation
```

#### 4. Watermarking Challenges

**English**: Well-studied, tools available
**Chinese**: Limited research, challenges include:
- Larger vocabulary size
- Different tokenization schemes
- Fewer watermarking implementations

### Practical Detection Pipeline for Chinese

```python
import jieba
import numpy as np
from collections import Counter

class ChineseAIDetector:
    def __init__(self):
        # Load Chinese AI vocabulary
        self.ai_vocab = self._load_chinese_ai_vocab()

    def detect(self, text):
        # 1. Word segmentation
        words = list(jieba.cut(text))

        # 2. Vocabulary density
        ai_count = self._count_ai_words(text)

        # 3. Burstiness analysis
        sentences = self._split_sentences(text)
        burstiness = self._calculate_burstiness(sentences)

        # 4. Formulaic patterns
        formulaic = self._detect_formulaic(text)

        # 5. Combine scores
        score = self._combine_scores(
            ai_count, burstiness, formulaic
        )

        return score

    def _load_chinese_ai_vocab(self):
        return {
            'connection': ['此外', '同时', '另外', '再者'],
            'adjective': ['重要的', '关键的', '核心的'],
            'verb': ['体现', '反映', '表明', '展现']
        }
```

### Detection Thresholds for Chinese

Based on empirical analysis of Chinese academic writing:

| Metric | Safe | Caution | High Risk |
|--------|------|---------|-----------|
| AI词汇密度 | <30/1000字 | 30-50/1000字 | >50/1000字 |
| 句长变异系数 | >0.25 | 0.15-0.25 | <0.15 |
| 词汇多样性 | 0.5-0.7 | 0.4-0.5或0.7-0.8 | <0.4或>0.8 |
| 公式化比例 | <10% | 10-30% | >30% |

### Future Directions

#### 1. Chinese Watermarking

Research needed:
- Develop Chinese-specific watermarking schemes
- Account for character-based vs word-based tokenization
- Test with popular Chinese LLMs (e.g., ERNIE, Pangu)

#### 2. Chinese Paraphrasing Detection

Tools to investigate:
- Chinese paraphrase models
- Translation-based paraphrasing
- Style transfer techniques

#### 3. Cross-lingual Detection

Opportunities:
- Detect AI translation from English to Chinese
- Identify mixed AI-human writing
- Leverage multilingual models

### Recommended Tools for Chinese

1. **Word Segmentation**:
   - `jieba`: Fast and accurate
   - `pkuseg`: Peking University segmenter
   - `LTP`: Harbin Institute of Technology

2. **Language Models**:
   - `bert-base-chinese`: For feature extraction
   - `roberta-wwm-ext`: For classification
   - `ERNIE`: Baidu's enhanced model

3. **Detection Libraries**:
   - Custom implementations (see `scripts/`)
   - Adapted English detectors
   - Multilingual approaches

### References for Chinese Detection

1. **Chinese AI Writing Characteristics**:
   - See `chinese-resources.md` for detailed analysis

2. **Chinese NLP Tools**:
   - jieba: https://github.com/fxsjy/jieba
   - pkuseg: https://github.com/lancopku/pkuseg

3. **Chinese LLMs**:
   - ERNIE (Baidu)
   - Pangu (Huawei)
   - ChatGLM (Tsinghua)

---

## Implementation Notes

### Running the Reference Code

To experiment with the original research code:

```bash
cd docs/derector/

# Install dependencies
pip install -r requirements.txt

# Train TV estimation model
python impossibility/roberta_tv.py webtext small-117M \
    --data_dir data/ \
    --tv_model roberta-large \
    --batch_size 20

# Evaluate paraphrasing attacks
python rephrase/detect.py

# Generate adversarial examples
python pair-distribution/manual_generation.py
```

**Note**: The original code is designed for English text and requires specific dataset formats.

### Adapting for Chinese Usage

The scripts in `src/skills/ai-detector/scripts/` are adapted implementations:

1. `detect_paraphrasing.py` - Paraphrasing attack detection (Chinese)
2. `comprehensive_detector.py` - Multi-method detection (Chinese)
3. `batch_detector.py` - Batch processing tool

These scripts:
- Use jieba for Chinese word segmentation
- Include Chinese-specific vocabulary
- Adapt statistical thresholds for Chinese
- Provide Chinese language output

### Limitations

1. **Language Specific**: Original research is English-focused
2. **Model Dependencies**: Requires large language models
3. **Computational Cost**: TV estimation is expensive
4. **Data Requirements**: Needs training datasets

### Best Practices

1. **Start Simple**: Use vocabulary and burstiness first
2. **Add Complexity Gradually**: Incorporate advanced methods as needed
3. **Validate Results**: Cross-check with multiple tools
4. **Human Review**: Always include human judgment
5. **Continuous Learning**: Stay updated on new research