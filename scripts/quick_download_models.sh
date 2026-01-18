#!/bin/bash

###############################################################################
# Docling 模型快速下载脚本
#
# 这是一个简化的 bash 脚本，用于快速下载 Docling 所需的模型。
# 使用国内镜像站加速下载。
#
# 使用方法:
#   ./quick_download_models.sh                    # 下载到默认目录
#   ./quick_download_models.sh -d /path/to/models # 指定下载目录
#   ./quick_download_models.sh -e https://mirror.com  # 指定镜像地址
###############################################################################

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认配置
DEFAULT_OUTPUT_DIR="$HOME/.cache/docling/models"
DEFAULT_ENDPOINT="https://hf-mirror.com"
MODELS=(
    "docling-project/docling-layout-old:layout-model"
    "docling-project/docling-models:table-structure-model"
    "docling-project/docling-models:code-formula-model"
    "docling-project/docling-models:picture-classifier"
)

# 解析命令行参数
OUTPUT_DIR="$DEFAULT_OUTPUT_DIR"
ENDPOINT="$DEFAULT_ENDPOINT"
FORCE_DOWNLOAD=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -e|--endpoint)
            ENDPOINT="$2"
            shift 2
            ;;
        -f|--force)
            FORCE_DOWNLOAD=true
            shift
            ;;
        -h|--help)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  -d, --output-dir DIR    指定下载目录 (默认: $DEFAULT_OUTPUT_DIR)"
            echo "  -e, --endpoint URL      指定镜像地址 (默认: $DEFAULT_ENDPOINT)"
            echo "  -f, --force             强制重新下载已存在的模型"
            echo "  -h, --help              显示帮助信息"
            echo ""
            echo "示例:"
            echo "  $0                                  # 使用默认配置"
            echo "  $0 -d /my/models -e https://hf-mirror.com"
            echo "  $0 --force                          # 强制重新下载"
            exit 0
            ;;
        *)
            echo -e "${RED}未知参数: $1${NC}"
            echo "使用 -h 或 --help 查看帮助"
            exit 1
            ;;
    esac
done

# 打印配置信息
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Docling 模型快速下载工具${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "下载目录: ${GREEN}${OUTPUT_DIR}${NC}"
echo -e "镜像地址: ${GREEN}${ENDPOINT}${NC}"
if [ "$FORCE_DOWNLOAD" = true ]; then
    echo -e "强制下载: ${YELLOW}是${NC}"
fi
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查 Python 和 huggingface_hub
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}错误: 未找到 python3${NC}"
    exit 1
fi

echo -e "${YELLOW}检查依赖...${NC}"
python3 -c "import huggingface_hub" 2>/dev/null || {
    echo -e "${RED}错误: 未安装 huggingface_hub${NC}"
    echo -e "${YELLOW}请运行: pip install huggingface_hub${NC}"
    exit 1
}
echo -e "${GREEN}✓ 依赖检查通过${NC}"
echo ""

# 创建下载目录
echo -e "${YELLOW}创建下载目录...${NC}"
mkdir -p "$OUTPUT_DIR"
echo -e "${GREEN}✓ 目录创建成功${NC}"
echo ""

# 下载函数
download_model() {
    local repo_id=$1
    local folder_name=$2
    local output_path="$OUTPUT_DIR/$folder_name"
    
    echo -e "${BLUE}下载模型: $repo_id${NC}"
    
    if [ -d "$output_path" ] && [ "$FORCE_DOWNLOAD" = false ]; then
        echo -e "${YELLOW}  → 模型已存在，跳过${NC}"
        return 0
    fi
    
    # 构建下载命令
    local cmd="python3 << 'EOF'
from huggingface_hub import snapshot_download
from pathlib import Path

try:
    download_path = snapshot_download(
        repo_id='$repo_id',
        local_dir='$output_path',
        endpoint='$ENDPOINT',
        force_download=$FORCE_DOWNLOAD,
    )
    print(f'✓ 下载成功: {download_path}')
except Exception as e:
    print(f'✗ 下载失败: {e}')
    exit(1)
EOF"
    
    # 执行下载
    if eval "$cmd"; then
        echo -e "${GREEN}  ✓ 下载完成${NC}"
        return 0
    else
        echo -e "${RED}  ✗ 下载失败${NC}"
        return 1
    fi
}

# 下载所有模型
echo -e "${YELLOW}开始下载模型...${NC}"
echo ""

SUCCESS_COUNT=0
FAILED_COUNT=0

for model in "${MODELS[@]}"; do
    IFS=':' read -ra PARTS <<< "$model"
    REPO_ID="${PARTS[0]}"
    FOLDER_NAME="${PARTS[1]}"
    
    if download_model "$REPO_ID" "$FOLDER_NAME"; then
        ((SUCCESS_COUNT++))
    else
        ((FAILED_COUNT++))
    fi
    echo ""
done

# 打印摘要
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}下载摘要${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "成功: ${GREEN}${SUCCESS_COUNT}${NC}"
echo -e "失败: ${RED}${FAILED_COUNT}${NC}"
echo -e "总计: $((SUCCESS_COUNT + FAILED_COUNT))"
echo -e "${BLUE}========================================${NC}"
echo ""

# 显示下载目录内容
echo -e "${YELLOW}下载目录内容:${NC}"
ls -lh "$OUTPUT_DIR" | awk '{print $9, $5}'

echo ""
if [ $FAILED_COUNT -eq 0 ]; then
    echo -e "${GREEN}✓ 所有模型下载完成！${NC}"
    exit 0
else
    echo -e "${RED}✗ 部分模型下载失败，请检查网络连接${NC}"
    exit 1
fi