# Web Reader 技能安装和配置指南

## 安装依赖

### 1. 安装Python包依赖

```bash
pip install -r /skills/web-reader/requirements.txt
```

或者手动安装：

```bash
pip install requests beautifulsoup4 markdownify playwright
```

### 2. 安装Playwright浏览器

```bash
playwright install chromium
```

### 3. （可选）配置Jina Reader API密钥

如果需要使用Jina Reader的高级功能，可以配置API密钥：

```bash
export JINA_READER_API_KEY="your-api-key-here"
```

或者在代码中设置：

```python
import os
os.environ["JINA_READER_API_KEY"] = "your-api-key-here"
```

## 验证安装

运行测试脚本来验证安装是否成功：

```bash
cd /skills/web-reader
python test_web_reader.py
```

## 基本使用

```python
from web_reader import fetch_url

# 智能获取网页内容
result = fetch_url("https://example.com")
print(result.content)
```

## 故障排除

### 常见问题

1. **Playwright浏览器未安装**
   - 错误信息: `BrowserType.launch: Failed to launch browser`
   - 解决方案: 运行 `playwright install chromium`

2. **网络连接超时**
   - 错误信息: `请求超时（30秒）`
   - 解决方案: 检查网络连接，或尝试使用不同的解析方法

3. **SSL证书错误**
   - 解决方案: 对于内部网站，可以修改 `web_reader.py` 中的请求参数添加 `verify=False`

### 性能优化

- **批量处理**: 使用 `fetch_multiple_urls` 来同时处理多个URL
- **方法选择**: 对于简单网站，直接使用 `fetch_url_local` 可以提高速度
- **资源限制**: 批量处理时限制URL数量不超过10个

## 环境要求

- Python 3.8+
- 网络连接（用于访问外部网站）
- 足够的内存（Playwright浏览器需要约100-200MB内存）

## 许可证

MIT License