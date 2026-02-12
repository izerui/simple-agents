---
name: bing-url-rules
description: Bing 网站 URL 结构和路径规范。定义 Bing 搜索引擎的 URL 结构、可访问路径和参数规则。用于网络爬虫、数据采集和搜索引擎优化相关任务，支持访问 Bing 各类服务（搜索、图片、视频、地图、新闻等）。
---

# Bing URL 层级访问规则

## 概述

本技能定义 Microsoft Bing 网站的 URL 结构和访问规则，帮助规范化和控制对 Bing 服务的访问。

## 基础 URL 结构

### 主域名
- `https://www.bing.com` - 全球主站
- `https://bing.com` - 简化域名（重定向至 www）

### 市场/语言参数
URL 通过 `mkt` 参数指定市场区域：
- `mkt=en-US` - 英语（美国）
- `mkt=zh-CN` - 简体中文（中国）
- `mkt=ja-JP` - 日语（日本）
- `mkt=ar-XA` - 阿拉伯语

### 国内版 vs 国际版

**国内版（中国区）：**
```
https://www.bing.com/?toWww=1&redig=9ED816754DDD4456890BC64ABCB218A0&FORM=BEHPTB
```

**国际版：**
```
https://www.bing.com/?toWww=1&redig=9ED816754DDD4456890BC64ABCB218A0&FORM=BEHPTB&ensearch=1
```

**区别说明：**
- 国内版：搜索结果符合中国法规，部分内容受限
- 国际版：完整搜索结果，无内容过滤
- 通过 `ensearch=1` 参数强制切换到国际版

## 主要服务路径

| 路径 | 说明 | 示例 |
|------|------|------|
| `/` | 主页 | https://www.bing.com/ |
| `/search` | 网页搜索 | https://www.bing.com/search?q=keyword |
| `/images/search` | 图片搜索 | https://www.bing.com/images/search?q=keyword |
| `/videos/search` | 视频搜索 | https://www.bing.com/videos/search?q=keyword |
| `/news/search` | 新闻搜索 | https://www.bing.com/news/search?q=keyword |
| `/maps` | 地图服务 | https://www.bing.com/maps |
| `/travel` | 旅行服务 | https://www.bing.com/travel |
| `/shopping` | 购物 | https://www.bing.com/shopping |

## 搜索参数

### 通用搜索参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `q` | 搜索查询词 | `q=python+tutorial` |
| `mkt` | 市场区域 | `mkt=zh-CN` |
| `count` | 结果数量 | `count=20` |
| `offset` | 结果偏移 | `offset=20` |
| `form` | 表单来源 | `form=HPFBBK` |
| `ssd` | 会话日期 | `ssd=20260211_0800` |

### 搜索结果过滤参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `filters` | 结果过滤 | `filters=ex1:"ez1"` |
| `pq` | 解析后的查询 | `pq=python+tutorial` |
| `sc` | 搜索类别 | `sc=0-0` |
| `sp` | 搜索参数 | `sp=-1` |
| `qs` | 查询状态 | `qs=n` |
| `sk` | 搜索键 | `sk=1` |

## 特殊 URL 模式

### 图片详情页

**基础 URL：** `https://www.bing.com/images/detail`

**主要参数：**

| 参数 | 说明 | 示例 |
|------|------|------|
| `search` | 搜索上下文 | 编码的搜索参数 |
| `id` | 图片 ID | 图片唯一标识符 |

**完整示例：**
```
https://www.bing.com/images/detail?search=python&qft=+filterui:imagesize-large
```

**作用：** 查看大图、来源网站、相关图片、尺寸信息等

### 视频详情页

**基础 URL：** `https://www.bing.com/videos/detail`

**主要参数：**

| 参数 | 说明 | 示例 |
|------|------|------|
| `v` | 视频 ID | 视频唯一标识符 |

**完整示例：**
```
https://www.bing.com/videos/detail?v=abc123xyz
```

**作用：** 直接播放视频、查看详细信息、相关视频推荐

### 新闻文章页

**基础 URL：** `https://www.bing.com/news`

**主要参数：**

| 参数 | 说明 | 示例 |
|------|------|------|
| `q` | 搜索关键词 | `q=technology` |
| `category` | 新闻类别 | `category=politics` |

**完整示例：**
```
https://www.bing.com/news/search?q=artificial+intelligence
https://www.bing.com/news?category=world
```

**支持类别：** 政治、商业、科技、体育、娱乐、健康、科学

**作用：** 浏览头条新闻、按类别查看、搜索历史新闻

### 翻译服务

**基础 URL：** `https://www.bing.com/translator`

**主要参数：**

| 参数 | 说明 | 示例 |
|------|------|------|
| `from` | 源语言 | `from=en` |
| `to` | 目标语言 | `to=zh-CN` |
| `text` | 翻译文本 | `text=hello` |

**完整示例：**
```
https://www.bing.com/translator/?from=en&to=zh-CN&text=hello
https://www.bing.com/translator/?from=zh-CN&to=en&text=%E4%BD%A0%E5%A5%BD
```

**支持语言：** 100+ 种语言，包括中文、英语、日语、韩语、法语、德语、西班牙语等

**作用：**
- 文本实时翻译
- 网页内容翻译
- 支持语音输入和输出
- 历史记录保存

**使用方式：**
1. 直接访问翻译页面手动输入
2. 通过 URL 参数传入翻译内容
3. 支持双语对话模式

### 字典服务

**基础 URL：** `https://www.bing.com/dict`

**主要参数：**

| 参数 | 说明 | 示例 |
|------|------|------|
| `q` | 查询单词 | `q=hello` |
| `mkt` | 语言市场 | `mkt=zh-CN` |

**完整示例：**
```
https://www.bing.com/dict/search?q=hello
https://www.bing.com/dict?q=artificial&mkt=en-US
```

**作用：**
- 提供英汉、汉英双向翻译
- 显示单词发音（音标、音频）
- 提供例句和用法
- 显示词性变化和同义词

**使用方式：**
1. 直接访问首页进行词典查询
2. 通过 URL 参数直接搜索单词
3. 支持中英文互译
4. 返回 JSON 格式数据（需解析页面）

### 地图服务

**基础 URL：** `https://www.bing.com/maps`

**主要参数：**

| 参数 | 说明 | 示例 |
|------|------|------|
| `q` | 地点搜索 | `q=Beijing` |
| `cp` | 中心点 | `cp=39.9~116.4` |
| `lvl` | 缩放级别 | `lvl=12` |
| `style` | 地图样式 | `style=a` |

**完整示例：**
```
https://www.bing.com/maps?q=Beijing
https://www.bing.com/maps?cp=39.9~116.4&lvl=12
```

**路线规划：**
```
https://www.bing.com/maps/directions?from=Beijing&to=Shanghai
```

**作用：** 地点搜索、路线规划、交通状况、街景查看

### 旅行服务

**基础 URL：** `https://www.bing.com/travel`

**主要参数：**

| 参数 | 说明 | 示例 |
|------|------|------|
| `q` | 目的地 | `q=Tokyo` |

**完整示例：**
```
https://www.bing.com/travel?q=flight+to+Tokyo
```

**作用：** 航班搜索、酒店预订、旅行规划、价格比较

### 购物服务

**基础 URL：** `https://www.bing.com/shopping`

**主要参数：**

| 参数 | 说明 | 示例 |
|------|------|------|
| `q` | 商品名称 | `q=iphone+15` |
| `price` | 价格范围 | `price=500..1000` |

**完整示例：**
```
https://www.bing.com/shopping?q=laptop
https://www.bing.com/shopping?q=headphone&price=50..200
```

**作用：** 商品搜索、价格比较、商家评分、购买链接

## 高级搜索模式

### 搜索运算符

| 运算符 | 说明 | 示例 |
|--------|------|------|
| `site:` | 站内搜索 | `site:github.com python` |
| `filetype:` | 文件类型 | `filetype:pdf machine learning` |
| `intitle:` | 标题包含 | `intitle:"open source" project` |
| `inurl:` | URL 包含 | `inurl:blog tutorial` |
| `intext:` | 正文包含 | `intext:keyword` |

**示例：**
```
https://www.bing.com/search?q=site:github.com+python
https://www.bing.com/search?q=filetype:pdf+machine+learning
https://www.bing.com/search?q=intitle:"open+source"+project
```

## 图片搜索过滤器

### 尺寸过滤器

| 参数 | 说明 |
|------|------|
| `filterui:imagesize-large` | 大图 |
| `filterui:imagesize-medium` | 中图 |
| `filterui:imagesize-small` | 小图 |
| `filterui:imagesize-wallpaper` | 壁纸尺寸 |
| `filterui:imagesize-custom` | 自定义尺寸 |

**示例：**
```
https://www.bing.com/images/search?q=nature&qft=+filterui:imagesize-wallpaper
```

### 颜色过滤器

| 参数 | 说明 |
|------|------|
| `filterui:color2-bw` | 黑白 |
| `filterui:color2-color` | 彩色 |
| `filterui:color2-red` | 红色 |
| `filterui:color2-blue` | 蓝色 |
| `filterui:color2-black` | 黑色主导 |

### 类型过滤器

| 参数 | 说明 |
|------|------|
| `filterui:photo-clipart` | 剪贴画 |
| `filterui:photo-lineart` | 线条画 |
| `filterui:photo-animatedgif` | 动画 GIF |
| `filterui:photo-transparent` | 透明背景 |

### 授权过滤器

| 参数 | 说明 |
|------|------|
| `filterui:license-free` | 免费使用 |
| `filterui:license-cc` | Creative Commons |
| `filterui:license-public` | 公共领域 |

**完整示例：**
```
https://www.bing.com/images/search?q=logo&qft=+filterui:license-free
```

## 视频搜索过滤器

### 时长过滤器

| 参数 | 说明 |
|------|------|
| `filterui:duration-short` | < 5 分钟 |
| `filterui:duration-medium` | 5-20 分钟 |
| `filterui:duration-long` | > 20 分钟 |

### 分辨率过滤器

| 参数 | 说明 |
|------|------|
| `filterui:resolution-hd` | 高清 |
| `filterui:resolution-4k` | 4K |

**完整示例：**
```
https://www.bing.com/videos/search?q=documentary&qft=+filterui:duration-long
```

## 新闻搜索过滤器

### 时间过滤器

| 参数 | 说明 |
|------|------|
| `filterui:day24` | 过去 24 小时 |
| `filterui:week7` | 过去一周 |
| `filterui:month1` | 过去一月 |

### 类别过滤器

| 参数 | 说明 |
|------|------|
| `filterui:cat1-tech` | 科技 |
| `filterui:cat1-biz` | 商业 |
| `filterui:cat1-spo` | 体育 |
| `filterui:cat1-pol` | 政治 |
| `filterui:cat1-ent` | 娱乐 |
| `filterui:cat1-hea` | 健康 |
| `filterui:cat1-sci` | 科学 |

**完整示例：**
```
https://www.bing.com/news/search?q=tech+news&qft=+filterui:day24
```

## 正则表达式模式

### 通用 Bing URL

```regex
https?://(www\.)?bing\.com(/.*)?
```

### 搜索 URL

```regex
https?://(www\.)?bing\.com/search\?q=[^&]+.*
```

### 图片搜索

```regex
https?://(www\.)?bing\.com/images/search\?q=[^&]+.*
```

### 视频搜索

```regex
https?://(www\.)?bing\.com/videos/search\?q=[^&]+.*
```

### 新闻搜索

```regex
https?://(www\.)?bing\.com/news/search\?q=[^&]+.*
```

### 字典服务

```regex
https?://(www\.)?bing\.com/dict(/search)?\?q=[^&]+.*
```

### 购物服务

```regex
https?://(www\.)?bing\.com/shopping\?q=[^&]+.*
```

### 旅行服务

```regex
https?://(www\.)?bing\.com/travel(/.*)?
```

## URL 编码注意事项

### 常见字符编码

| 原字符 | 编码后 |
|--------|--------|
| 空格 | `+` 或 `%20` |
| 中文 | `%E4%B8%AD%E6%96%87` (UTF-8) |
| `&` | `%26` |
| `=` | `%3D` |
| `?` | `%3F` |
| `#` | `%23` |
| `/` | `%2F` |
| `:` | `%3A` |

### Python 编码示例

```python
from urllib.parse import quote_plus

query = "人工智能 教程"
encoded = quote_plus(query)
# result: %E4%BA%BA%E5%B7%A5%E6%99%BA%E8%83%BD+%E6%95%99%E7%A8%8B

url = f"https://www.bing.com/search?q={encoded}"
```
