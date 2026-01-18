#!/bin/bash

# Docling 模型下载脚本
# 直接使用 docling 的下载功能

OUTPUT_DIR="${1:-./models}"
ENDPOINT="https://hf-mirror.com"

echo "使用镜像: $ENDPOINT"
echo "输出目录: $OUTPUT_DIR"
echo ""

# 设置环境变量
export HF_ENDPOINT="$ENDPOINT"
export HF_HOME="$OUTPUT_DIR"

# 使用 Python 调用 docling 的下载功能
python3 << 'EOF'
import os
from pathlib import Path

# 设置缓存目录
cache_dir = Path(os.getenv("OUTPUT_DIR", "./models")).resolve()
os.environ["HF_HOME"] = str(cache_dir)
os.environ["HF_ENDPOINT"] = os.getenv("HF_ENDPOINT", "https://hf-mirror.com")

print(f"缓存目录: {cache_dir}")
print(f"镜像地址: {os.getenv('HF_ENDPOINT')}")
print()

# 导入 docling 的下载工具
from docling.utils.model_downloader import download_models

# 下载所有核心模型
output_path = download_models(
    output_dir=cache_dir / "models",
    force=False,
    progress=True,
    with_layout=True,
    with_tableformer=True,
    with_code_formula=True,
    with_picture_classifier=True,
    with_rapidocr=True,
    with_easyocr=False,
)

print()
print("=" * 50)
print("所有模型下载完成！")
print("=" * 50)
print(f"位置: {output_path}")
print()
print("使用方法:")
print("  from docling.document_converter import DocumentConverter")
print("  from pathlib import Path")
print(f"  converter = DocumentConverter(artifacts_path=Path('{cache_dir / 'models'}'))")
EOF