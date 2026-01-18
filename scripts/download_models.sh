#!/bin/bash

# Docling 核心模型下载脚本
# 使用方法: ./download_core_models.sh [输出目录]

OUTPUT_DIR="${1:-./models}"
ENDPOINT="https://hf-mirror.com"

echo "使用镜像: $ENDPOINT"
echo "输出目录: $OUTPUT_DIR"
echo ""

export HF_ENDPOINT="$ENDPOINT"
export HF_HOME="$OUTPUT_DIR"

python3 << 'EOF'
import os
from pathlib import Path

# 设置环境变量
cache_dir = Path(os.getenv("OUTPUT_DIR", "./models")).resolve()
os.environ["HF_HOME"] = str(cache_dir)
os.environ["HF_ENDPOINT"] = os.getenv("HF_ENDPOINT", "https://hf-mirror.com")

print(f"缓存目录: {cache_dir}")
print(f"镜像地址: {os.getenv('HF_ENDPOINT')}")
print()

from huggingface_hub import snapshot_download

# 要下载的模型仓库
REPOS = [
    "docling-project/CodeFormulaV2",
    "docling-project/docling-layout-heron",
    "docling-project/docling-models",
]

print("=" * 60)
print("开始下载模型...")
print("=" * 60)
print()

for repo_id in REPOS:
    print(f"下载: {repo_id}")
    
    try:
        download_path = snapshot_download(
            repo_id=repo_id,
            endpoint=os.getenv("HF_ENDPOINT"),
            cache_dir=cache_dir,
        )
        
        # 统计文件
        file_count = sum(1 for _ in Path(download_path).rglob("*") if _.is_file())
        total_size = sum(f.stat().st_size for f in Path(download_path).rglob("*") if f.is_file())
        size_mb = total_size / (1024 * 1024)
        
        print(f"  ✓ 下载完成 ({file_count} 个文件, {size_mb:.1f} MB)")
        print()
    except Exception as e:
        print(f"  ✗ 下载失败: {e}")
        print()

print("=" * 60)
print("所有模型下载完成！")
print("=" * 60)
print(f"位置: {cache_dir}")
print()
print("使用方法:")
print("  export HF_HOME=./models")
print("  from docling.document_converter import DocumentConverter")
print("  converter = DocumentConverter()")
EOF