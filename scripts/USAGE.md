# Docling 模型下载工具 - 快速使用指南

## 🚀 快速开始（推荐）

### 下载所有核心模型（使用国内镜像）

```bash
python scripts/download_docling_models.py --endpoint https://hf-mirror.com
```

### 或者使用更简单的 bash 脚本

```bash
./scripts/quick_download_models.sh
```

## 📁 常用命令

### 1. 下载到自定义目录

```bash
python scripts/download_docling_models.py \
  --output-dir ./my_models \
  --endpoint https://hf-mirror.com
```

### 2. 只下载特定模型

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

### 3. 查看所有可用模型

```bash
python scripts/download_docling_models.py --list-models
```

### 4. 强制重新下载

```bash
python scripts/download_docling_models.py \
  --force \
  --endpoint https://hf-mirror.com
```

## 🔧 在代码中使用

### 方式 1：使用默认缓存目录

模型会自动下载到 `~/.cache/docling/models/`，直接使用即可：

```python
from docling.document_converter import DocumentConverter

converter = DocumentConverter()
result = converter.convert("your_document.pdf")
```

### 方式 2：指定自定义模型目录

```python
from docling.document_converter import DocumentConverter
from pathlib import Path

converter = DocumentConverter(
    artifacts_path=Path("./my_models")
)
result = converter.convert("your_document.pdf")
```

### 方式 3：在 Docker 容器中使用

```python
import os
from pathlib import Path
from docling.document_converter import DocumentConverter

# 使用环境变量中的路径
model_dir = Path(os.getenv("HF_HOME", "~/.cache/huggingface"))
converter = DocumentConverter(artifacts_path=model_dir)
```

## 🐳 Docker 使用

### 方法 1：挂载预下载的模型

```bash
# 1. 先本地下载模型
python scripts/download_docling_models.py \
  --output-dir ./data/huggingface \
  --endpoint https://hf-mirror.com

# 2. 启动 Docker（挂载模型目录）
docker-compose up
```

### 方法 2：在 Dockerfile 中预下载

```dockerfile
RUN pip install huggingface_hub docling
COPY scripts/download_docling_models.py /tmp/
RUN python /tmp/download_docling_models.py \
  --endpoint https://hf-mirror.com \
  --output-dir /app/models
ENV HF_HOME=/app/models
```

## 💡 常见场景

### 场景 1：首次使用，需要下载所有模型

```bash
# 推荐使用国内镜像
./scripts/quick_download_models.sh -e https://hf-mirror.com
```

### 场景 2：已经下载过，但需要更新模型

```bash
# 强制重新下载
./scripts/quick_download_models.sh -e https://hf-mirror.com -f
```

### 场景 3：只处理 PDF，不需要 OCR

```bash
# 只下载布局模型
python scripts/download_docling_models.py \
  --models layout_model \
  --endpoint https://hf-mirror.com
```

### 场景 4：服务器环境，需要离线部署

```bash
# 1. 在有网络的机器上下载
python scripts/download_docling_models.py \
  --output-dir ./offline_models \
  --endpoint https://hf-mirror.com

# 2. 打包传输到服务器
tar -czf models.tar.gz offline_models/
scp models.tar.gz user@server:/path/

# 3. 在服务器上解压
tar -xzf models.tar.gz -C /path/to/deploy/
```

## ❓ 问题排查

### 下载速度慢

```bash
# 确保使用了国内镜像
python scripts/download_docling_models.py --endpoint https://hf-mirror.com
```

### 连接超时

```bash
# 尝试不同的镜像地址
python scripts/download_docling_models.py --endpoint https://hf-mirror.com
```

### 磁盘空间不足

```bash
# 只下载必需的模型
python scripts/download_docling_models.py \
  --models layout_model table_structure \
  --endpoint https://hf-mirror.com
```

### 验证模型是否下载成功

```bash
# 检查目录
ls -lh ~/.cache/docling/models/

# 或者在 Python 中验证
python -c "
from pathlib import Path
model_dir = Path('~/.cache/docling/models').expanduser()
print('模型目录:', model_dir)
print('包含的模型:', [d.name for d in model_dir.iterdir() if d.is_dir()])
"
```

## 📊 模型大小参考

| 模型 | 大小 | 用途 |
|------|------|------|
| layout_model | ~500MB | 文档布局分析（必需） |
| table_structure | ~300MB | 表格识别（必需） |
| code_formula | ~200MB | 代码/公式识别（可选） |
| picture_classifier | ~100MB | 图片分类（可选） |
| rapidocr | ~150MB | OCR 引擎（扫描文档需要） |

**核心模型总大小**：约 1.2GB

## 🎯 最佳实践

1. **首次使用**：先下载核心模型
   ```bash
   ./scripts/quick_download_models.sh
   ```

2. **生产环境**：预下载并打包部署
   ```bash
   python scripts/download_docling_models.py --output-dir ./prod_models
   tar -czf prod_models.tar.gz prod_models/
   ```

3. **开发环境**：使用默认缓存目录，方便测试
   ```python
   # 直接使用，模型会自动下载到 ~/.cache/docling/
   converter = DocumentConverter()
   ```

4. **Docker 部署**：在构建时预下载，避免运行时下载
   ```dockerfile
   RUN python scripts/download_docling_models.py \
     --endpoint https://hf-mirror.com \
     --output-dir /app/models
   ```

## 📞 获取帮助

```bash
# 查看详细帮助
python scripts/download_docling_models.py --help

# 或查看完整文档
cat scripts/README.md
```
