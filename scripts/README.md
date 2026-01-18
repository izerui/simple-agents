# Docling 模型下载工具

这是一个独立的 Docling 模型下载脚本，用于在 Docker 容器或本地环境中预先下载 Docling 所需的机器学习模型。

## 功能特性

✅ **支持自定义镜像地址** - 可以指定 HuggingFace 国内镜像站加速下载  
✅ **灵活的模型选择** - 支持下载全部模型、核心模型或指定特定模型  
✅ **进度显示** - 实时显示下载进度  
✅ **断点续传** - 支持中断后继续下载  
✅ **自定义下载目录** - 可以指定模型保存位置  

## 安装依赖

确保已安装 `huggingface_hub`：

```bash
pip install huggingface_hub
```

或者在 Dockerfile 中添加：

```dockerfile
RUN pip install huggingface_hub
```

## 使用方法

### 1. 基础使用

下载所有核心模型（推荐使用国内镜像）：

```bash
python scripts/download_docling_models.py --endpoint https://hf-mirror.com
```

### 2. 指定下载目录

```bash
python scripts/download_docling_models.py \
  --output-dir /path/to/your/models \
  --endpoint https://hf-mirror.com
```

### 3. 只下载特定模型

```bash
# 只下载布局模型
python scripts/download_docling_models.py \
  --models layout_model \
  --endpoint https://hf-mirror.com

# 下载多个模型
python scripts/download_docling_models.py \
  --models layout_model table_structure code_formula \
  --endpoint https://hf-mirror.com
```

### 4. 下载所有模型（包括可选的 VLM 模型）

```bash
python scripts/download_docling_models.py \
  --all \
  --endpoint https://hf-mirror.com
```

### 5. 列出所有可用模型

```bash
python scripts/download_docling_models.py --list-models
```

### 6. 强制重新下载

```bash
python scripts/download_docling_models.py \
  --force \
  --endpoint https://hf-mirror.com
```

## 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--endpoint` | str | None | HuggingFace 镜像地址，如 `https://hf-mirror.com` |
| `--output-dir` | Path | `~/.cache/docling/models` | 模型下载目录 |
| `--models` | str[] | 核心模型 | 指定要下载的模型名称 |
| `--all` | flag | False | 下载所有模型（包括可选的） |
| `--force` | flag | False | 强制重新下载已存在的模型 |
| `--no-progress` | flag | False | 不显示下载进度条 |
| `--list-models` | flag | False | 列出所有可用的模型 |

## 可用模型列表

### 核心模型（默认下载）

| 模型名称 | 模型 ID | 大小 | 用途 |
|----------|---------|------|------|
| `layout_model` | `docling-project/docling-layout-old` | ~500MB | 文档布局分析 |
| `table_structure` | `docling-project/docling-models` | ~300MB | 表格结构识别 |
| `code_formula` | `docling-project/docling-models` | ~200MB | 代码和公式识别 |
| `picture_classifier` | `docling-project/docling-models` | ~100MB | 图片分类 |
| `rapidocr_torch` | `RapidAI/RapidOCR` | ~100MB | OCR 引擎（PyTorch） |
| `rapidocr_onnx` | `RapidAI/RapidOCR` | ~50MB | OCR 引擎（ONNX） |

### 可选模型（需要通过 `--all` 或 `--models` 指定）

| 模型名称 | 模型 ID | 大小 | 用途 |
|----------|---------|------|------|
| `granite_docling` | `ibm-granite/granite-docling-258M` | ~500MB | Granite Docling VLM |
| `granite_vision` | `ibm-granite/granite-vision-3b-8bit` | ~3GB | Granite Vision 模型 |
| `smolvlm` | `HuggingFaceTB/SmolVLM-Instruct` | ~2GB | SmolVLM 模型 |

## 国内镜像推荐

以下是国内常用的 HuggingFace 镜像站：

- **hf-mirror.com**（推荐）：`https://hf-mirror.com`
- **官方镜像**：`https://hf-mirror.com`

## Docker 集成示例

### 方案 1：在 Dockerfile 中预下载

```dockerfile
FROM python:3.12-slim

# 安装依赖
RUN pip install huggingface_hub docling

# 复制下载脚本
COPY scripts/download_docling_models.py /tmp/

# 预下载模型到容器内
RUN python /tmp/download_docling_models.py \
  --endpoint https://hf-mirror.com \
  --output-dir /app/models

# 设置环境变量
ENV HF_HOME=/app/models
ENV HF_HUB_ENDPOINT=https://hf-mirror.com

# 清理临时文件
RUN rm /tmp/download_docling_models.py
```

### 方案 2：在 docker-compose.yml 中挂载

```yaml
services:
  simple-agents-api:
    image: serv999.com/hub/izerui/simple-agents:latest
    environment:
      # 使用挂载的模型目录
      HF_HOME: /deps/simple-agents/data/huggingface
      HF_HUB_ENDPOINT: https://hf-mirror.com
    volumes:
      # 挂载预下载的模型目录
      - ./data/huggingface:/deps/simple-agents/data/huggingface
```

然后在构建镜像前先运行：

```bash
# 本地下载模型
python scripts/download_docling_models.py \
  --output-dir ./data/huggingface \
  --endpoint https://hf-mirror.com

# 再构建 Docker 镜像
docker-compose build
```

### 方案 3：多阶段构建

```dockerfile
# 第一阶段：下载模型
FROM python:3.12-slim as model-downloader

RUN pip install huggingface_hub
COPY scripts/download_docling_models.py /tmp/
RUN python /tmp/download_docling_models.py \
  --endpoint https://hf-mirror.com \
  --output-dir /models

# 第二阶段：构建应用镜像
FROM python:3.12-slim

COPY --from=model-downloader /models /app/models
ENV HF_HOME=/app/models
ENV HF_HUB_ENDPOINT=https://hf-mirror.com

# 其他构建步骤...
```

## 常见问题

### Q1: 下载速度慢或超时怎么办？

**A:** 确保使用了国内镜像地址：

```bash
python scripts/download_docling_models.py --endpoint https://hf-mirror.com
```

### Q2: 如何确认模型下载成功？

**A:** 检查下载目录：

```bash
ls -lh ~/.cache/docling/models/
# 或你指定的目录
ls -lh /path/to/your/models/
```

每个模型文件夹下应该有模型文件（如 `model.safetensors`、`config.json` 等）。

### Q3: 如何在代码中指定模型路径？

**A:** 在初始化 `DocumentConverter` 时通过 `artifacts_path` 参数指定：

```python
from docling.document_converter import DocumentConverter
from pathlib import Path

converter = DocumentConverter(
    artifacts_path=Path("/path/to/your/models")
)
```

### Q4: 模型下载失败怎么办？

**A:** 尝试以下步骤：

1. 检查网络连接
2. 尝试不同的镜像地址
3. 使用 `--force` 参数强制重新下载
4. 分批下载模型，找出是哪个模型下载失败

### Q5: 下载过程中如何暂停？

**A:** 按 `Ctrl+C` 中断，下次运行时会自动续传。

## 注意事项

⚠️ **磁盘空间**：下载所有模型需要约 5-10GB 磁盘空间  
⚠️ **网络连接**：首次下载需要稳定的网络连接  
⚠️ **镜像兼容性**：某些镜像站可能不支持所有模型  
⚠️ **权限问题**：确保对下载目录有写权限  

## 完整示例

```bash
# 1. 列出所有模型
python scripts/download_docling_models.py --list-models

# 2. 下载核心模型到自定义目录
python scripts/download_docling_models.py \
  --output-dir ./models \
  --endpoint https://hf-mirror.com

# 3. 验证下载
ls -R ./models

# 4. 在代码中使用
python -c "
from docling.document_converter import DocumentConverter
from pathlib import Path

converter = DocumentConverter(
    artifacts_path=Path('./models')
)
print('✓ 模型加载成功！')
"
```

## 许可证

本脚本遵循与 Docling 相同的 MIT 许可证。

## 技术支持

如有问题，请参考 [Docling 官方文档](https://docling-project.github.io/docling/) 或提交 Issue。