#!/bin/bash

# Docling 模型下载脚本
# 使用方法: ./download_models.sh [输出目录]

OUTPUT_DIR="${1:-./models}"
ENDPOINT="https://hf-mirror.com"

echo "下载目录: $OUTPUT_DIR"
echo "镜像地址: $ENDPOINT"
echo ""

export HF_ENDPOINT="$ENDPOINT"
mkdir -p "$OUTPUT_DIR"

# 下载布局模型
echo "下载 layout-model..."
huggingface-cli download docling-project/docling-layout-old \
  --local-dir "$OUTPUT_DIR/layout-model"

# 下载表格结构模型
echo ""
echo "下载 table-structure-model..."
huggingface-cli download docling-project/docling-models table_structure/* \
  --local-dir "$OUTPUT_DIR/table-structure-model"

# 下载代码公式模型
echo ""
echo "下载 code-formula-model..."
huggingface-cli download docling-project/docling-models code_formula/* \
  --local-dir "$OUTPUT_DIR/code-formula-model"

# 下载图片分类模型
echo ""
echo "下载 picture-classifier..."
huggingface-cli download docling-project/docling-models picture_classifier/* \
  --local-dir "$OUTPUT_DIR/picture-classifier"

# 下载 OCR 模型
echo ""
echo "下载 rapidocr..."
huggingface-cli download RapidAI/RapidOCR \
  --local-dir "$OUTPUT_DIR/rapidocr"

echo ""
echo "✓ 所有模型下载完成！"
echo "位置: $OUTPUT_DIR"