# Web Reader 技能

## 概述
Web Reader 技能是一个强大的网页内容获取和解析工具，专为大语言模型设计。它能够智能地获取和解析任何网页内容，并将其转换为干净的 Markdown 格式。支持三重引擎策略（Jina Reader API、本地解析器、Playwright 浏览器），具有智能降级机制，能够突破各种访问限制。

## 功能特点
- 🚀 **三引擎支持**：集成 Jina Reader API、本地 HTML 解析器和 Playwright 浏览器
- 🔄 **智能降级**：Jina Reader → 本地解析 → Playwright 浏览器三层自动切换
- 🌐 **突破限制**：使用 Playwright 处理 Cloudflare、验证码等访问限制
- 📦 **批量处理**：支持同时获取多个 URL
- 🎯 **灵活控制**：可选择强制使用特定解析方式
- 📝 **Markdown 输出**：自动转换为清晰的 Markdown 格式

## 支持的受限网站类型
✅ **微信公众号文章** - 自动绕过访问限制  
✅ **时代杂志、纽约时报** - 突破付费墙和地区限制  
✅ **Cloudflare 保护网站** - 通过真实浏览器绕过检测  
✅ **需要 JavaScript 渲染的页面** - 完整执行页面脚本  
✅ **有验证码/人机验证的网站** - 模拟真实用户行为

## 使用方法

### 1. 智能获取（推荐）
```python
from web_reader import fetch_url

# 自动三层降级：Jina Reader → 本地解析 → Playwright 浏览器
result = fetch_url("https://example.com")
print(result.content)
```

### 2. 批量获取
```python
from web_reader import fetch_multiple_urls

urls = ["https://example1.com", "https://example2.com", "https://example3.com"]
results = fetch_multiple_urls(urls)
for result in results:
    print(f"URL: {result.url}")
    print(f"Content: {result.content[:100]}...")
```

### 3. 强制使用 Jina Reader
```python
from web_reader import fetch_url_with_jina

result = fetch_url_with_jina("https://example.com")
```

### 4. 强制使用本地解析器
```python
from web_reader import fetch_url_local

result = fetch_url_local("https://example.com")
```

### 5. 强制使用浏览器模式
```python
from web_reader import fetch_url_with_browser

result = fetch_url_with_browser("https://example.com")
```

## 安装依赖
在使用此技能前，请确保安装以下依赖：

```bash
pip install requests beautifulsoup4 markdownify playwright
playwright install chromium
```

## 配置
如果需要使用 Jina Reader API，可以通过环境变量配置：
- `JINA_READER_API_KEY` (可选): Jina Reader API 密钥

## 返回结果格式
所有函数返回一个 `WebContent` 对象，包含以下属性：
- `title`: 网页标题
- `content`: 转换后的 Markdown 内容
- `url`: 原始 URL
- `fetched_at`: 获取时间
- `content_length`: 内容长度
- `method`: 使用的解析方法

## 错误处理
- 如果所有方法都失败，会抛出 `WebReaderError` 异常
- 网络超时默认为 30 秒
- URL 验证会检查是否为有效的 HTTP/HTTPS URL