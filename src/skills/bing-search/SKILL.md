---
name: bing-search
description: Microsoft Bing 搜索引擎 URL 构建技能。支持六类搜索服务（网页、图片、视频、学术、词典、地图）的 URL 生成和参数配置。使用时机：需要构建 Bing 搜索 URL、配置搜索参数（时间过滤、尺寸筛选、排序等）、处理搜索分页、或进行网络爬虫开发时调用此技能。支持国内版/国际版切换，完整的筛选器参数组合。
allowed-tools:
  - fetch_url
---

# Bing 搜索 URL 规范

## 基础配置

### 主域名
- `https://www.bing.com` - 全球主站
- `https://bing.com` - 简化域名（重定向至 www）

### 国内版 vs 国际版
- **国内版**：默认，符合中国法规
- **国际版**：添加 `&ensearch=1` 参数

### 市场/语言参数
| 参数 | 说明 |
|------|------|
| `mkt=zh-CN` | 简体中文（中国） |
| `mkt=en-US` | 英语（美国） |
| `mkt=ja-JP` | 日语（日本） |

---

## 搜索结果处理（重要）

当使用 `fetch_url` 工具获取 Bing 搜索结果页面时：

1. 搜索结果列表中的链接是用来进一步访问和研究用的
2. 不要只停留在搜索结果页面，必须继续访问相关链接获取详细信息
3. **自行判断结果优先级**：根据标题、摘要、来源权威性判断优先级
4. 优先级判断标准：
   - 来源权威性：官方网站、知名媒体、学术机构优先
   - 内容相关性：标题和摘要与问题匹配度高优先
   - 时效性：新闻类问题优先选择最新发布的内容
   - 内容深度：优先选择看起来有详细内容的页面
5. 按优先级依次访问 3-5 个最相关的链接
6. 综合多个来源的信息，给出全面准确的回答

---

## 一、网页搜索

### 基础 URL

```
https://www.bing.com/search?q=关键词
```

### 核心参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `q` | 搜索关键词 | `q=世界旅游胜地` |
| `filters` | 时间过滤 | `filters=ex1:"ez1"` |
| `first` | 起始位置 | `first=1`（第1页），`first=11`（第2页） |
| `mkt` | 市场区域 | `mkt=zh-CN` |

### 时间过滤参数

| 时间范围 | filters 参数值 |
|----------|---------------|
| 时间不限 | 无 |
| 24小时内 | `filters=ex1:"ez1"` |
| 一周内 | `filters=ex1:"ez2"` |
| 一个月内 | `filters=ex1:"ez3"` |
| 三个月内 | `filters=ex1:"ez4"` |
| 一年内 | `filters=ex1:"ez5"` |
| 去年 | `filters=ex1:"ez5_20131_20496"` |

### 分页规律

每页 10 条结果：
- 第1页：`first=1`
- 第2页：`first=11`
- 第3页：`first=21`
- 第n页：`first=(n-1)*10+1`

### 搜索运算符

| 运算符 | 说明 | 示例 |
|--------|------|------|
| `site:` | 站内搜索 | `q=site:github.com python` |
| `filetype:` | 文件类型 | `q=filetype:pdf 机器学习` |
| `intitle:` | 标题包含 | `q=intitle:"开源"` |

### 完整 URL 示例

**基础搜索（时间不限）：**
```
https://www.bing.com/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0
```

**24小时内 + 分页：**
```
# 第1页
https://www.bing.com/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&filters=ex1%3a%22ez1%22&first=1

# 第2页
https://www.bing.com/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&filters=ex1%3a%22ez1%22&first=11

# 第3页
https://www.bing.com/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&filters=ex1%3a%22ez1%22&first=21
```

**去年搜索：**
```
https://www.bing.com/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&filters=ex1%3a%22ez5_20131_20496%22
```

---

## 二、图片搜索

### 基础 URL

```
https://www.bing.com/images/search?q=关键词
```

### 核心参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `q` | 搜索关键词 | `q=nature` |
| `qft` | 筛选器 | `qft=+filterui:imagesize-large` |
| `first` | 分页偏移 | `first=1` |

### qft 筛选器语法

```
qft=+filterui:类别-选项
```

组合多个筛选器：
```
qft=+filterui:imagesize-large+filterui:color2-color
```

### 尺寸过滤器

| 参数 | 说明 |
|------|------|
| `filterui:imagesize-small` | 小图 |
| `filterui:imagesize-medium` | 中图 |
| `filterui:imagesize-large` | 大图 |
| `filterui:imagesize-wallpaper` | 壁纸尺寸 |

### 颜色过滤器

| 参数 | 说明 |
|------|------|
| `filterui:color2-bw` | 黑白 |
| `filterui:color2-color` | 彩色 |
| `filterui:color2-red` | 红色 |
| `filterui:color2-blue` | 蓝色 |
| `filterui:color2-green` | 绿色 |
| `filterui:color2-orange` | 橙色 |

### 类型过滤器

| 参数 | 说明 |
|------|------|
| `filterui:photo-photo` | 照片 |
| `filterui:photo-clipart` | 剪贴画 |
| `filterui:photo-linedrawing` | 素描 |
| `filterui:photo-animatedgif` | 动画 GIF |
| `filterui:photo-transparent` | 透明背景 |

### 布局过滤器

| 参数 | 说明 |
|------|------|
| `filterui:aspect-square` | 方形 (1:1) |
| `filterui:aspect-tall` | 竖版 |
| `filterui:aspect-wide` | 横版 |

### 人员内容过滤器

| 参数 | 说明 |
|------|------|
| `filterui:face-face` | 仅脸部 |
| `filterui:face-portrait` | 半身像 |

### 日期过滤器

| 参数 | 说明 |
|------|------|
| `filterui:age-lt1440` | 过去24小时（1440分钟） |
| `filterui:age-lt10080` | 过去一周（10080分钟） |
| `filterui:age-lt43200` | 过去一个月（43200分钟） |
| `filterui:age-lt525600` | 去年（525600分钟） |

### 授权过滤器

| 参数 | 说明 |
|------|------|
| `filterui:license-free` | 免费使用 |
| `filterui:license-cc` | Creative Commons |
| `filterui:license-public` | 公共领域 |

### 完整 URL 示例

**基础搜索（所有尺寸）：**
```
https://www.bing.com/images/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0
```

**按尺寸过滤：**
```
# 小图
https://www.bing.com/images/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&qft=+filterui:imagesize-small

# 大图
https://www.bing.com/images/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&qft=+filterui:imagesize-large

# 壁纸尺寸（特大图）
https://www.bing.com/images/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&qft=+filterui:imagesize-wallpaper
```

**按类型过滤：**
```
# 所有类型
https://www.bing.com/images/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0

# 照片
https://www.bing.com/images/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&qft=+filterui:photo-photo

# 剪贴画
https://www.bing.com/images/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&qft=+filterui:photo-clipart

# 素描
https://www.bing.com/images/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&qft=+filterui:photo-linedrawing

# 动画 GIF
https://www.bing.com/images/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&qft=+filterui:photo-animatedgif

# 透明背景
https://www.bing.com/images/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&qft=+filterui:photo-transparent
```

**按布局过滤（配合透明背景示例）：**
```
# 全部
https://www.bing.com/images/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&qft=+filterui:photo-transparent

# 方形 (1:1)
https://www.bing.com/images/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&qft=+filterui:photo-transparent+filterui:aspect-square

# 横版
https://www.bing.com/images/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&qft=+filterui:photo-transparent+filterui:aspect-wide

# 竖版
https://www.bing.com/images/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&qft=+filterui:photo-transparent+filterui:aspect-tall
```

**按人物过滤（配合透明背景+竖版示例）：**
```
# 全部
https://www.bing.com/images/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&qft=+filterui:photo-transparent+filterui:aspect-tall

# 仅脸部
https://www.bing.com/images/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&qft=+filterui:photo-transparent+filterui:aspect-tall+filterui:face-face

# 半身像
https://www.bing.com/images/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&qft=+filterui:photo-transparent+filterui:aspect-tall+filterui:face-portrait
```

**按日期过滤（配合透明背景+竖版+半身像示例）：**
```
# 全部
https://www.bing.com/images/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&qft=+filterui:photo-transparent+filterui:aspect-tall+filterui:face-portrait

# 过去24小时
https://www.bing.com/images/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&qft=+filterui:photo-transparent+filterui:aspect-tall+filterui:face-portrait+filterui:age-lt1440

# 过去一周
https://www.bing.com/images/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&qft=+filterui:photo-transparent+filterui:aspect-tall+filterui:face-portrait+filterui:age-lt10080

# 过去一个月
https://www.bing.com/images/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&qft=+filterui:photo-transparent+filterui:aspect-tall+filterui:face-portrait+filterui:age-lt43200

# 去年
https://www.bing.com/images/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&qft=+filterui:photo-transparent+filterui:aspect-tall+filterui:face-portrait+filterui:age-lt525600
```

**组合过滤（大尺寸 + 彩色）：**
```
https://www.bing.com/images/search?q=nature&qft=+filterui:imagesize-large+filterui:color2-color
```

### 图片链接提取

搜索结果中每张图片包含以下属性：

| 属性 | 说明 |
|------|------|
| `murl` | 原始图片 URL |
| `turl` | 缩略图 URL |
| `映像`/`sourceUrl` | 来源网页 URL |

```python
# 提取图片链接示例
import re
pattern = r'"murl":"([^"]+)"'
images = re.findall(pattern, html_content)
```

---

## 三、视频搜索

### 基础 URL

```
https://www.bing.com/videos/search?q=关键词
```

### 核心参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `q` | 搜索关键词 | `q=documentary` |
| `qft` | 筛选器 | `qft=+filterui:duration-long` |

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

### 完整 URL 示例

**基础搜索：**
```
https://www.bing.com/videos/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0
```

**按时长过滤：**
```
# 短视频 (< 5分钟)
https://www.bing.com/videos/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&qft=+filterui:duration-short

# 中等长度 (5-20分钟)
https://www.bing.com/videos/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&qft=+filterui:duration-medium

# 长视频 (> 20分钟)
https://www.bing.com/videos/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&qft=+filterui:duration-long
```

**按分辨率过滤：**
```
# 高清
https://www.bing.com/videos/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&qft=+filterui:resolution-hd

# 4K
https://www.bing.com/videos/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&qft=+filterui:resolution-4k
```

---

## 四、学术搜索

### 基础 URL

```
https://www.bing.com/academic/search?q=关键词
```

### 核心参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `q` | 搜索关键词 | `q=artificial+intelligence` |
| `sort` | 排序方式 | `sort=2` |

### 排序参数

| sort 值 | 说明 |
|---------|------|
| 无 | 相关性排序（默认） |
| `sort=2` | 时间倒序 |
| `sort=3` | 时间正序 |
| `sort=4` | 按引用数 |

### 完整 URL 示例

**相关性排序（默认）：**
```
https://www.bing.com/academic/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0
```

**时间倒序：**
```
https://www.bing.com/academic/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&sort=2
```

**时间正序：**
```
https://www.bing.com/academic/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&sort=3
```

**按引用数：**
```
https://www.bing.com/academic/search?q=%e4%b8%96%e7%95%8c%e6%97%85%e6%b8%b8%e8%83%9c%e5%9c%b0&sort=4
```

---

## 五、词典搜索

### 基础 URL

```
https://www.bing.com/dict/search?q=单词
```

### 核心参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `q` | 查询单词 | `q=hello` |
| `mkt` | 语言市场 | `mkt=zh-CN` |

### 功能说明

- 英汉、汉英双向翻译
- 显示单词发音（音标、音频）
- 提供例句和用法
- 显示词性变化和同义词

### 完整 URL 示例

**英文单词查询：**
```
https://www.bing.com/dict/search?q=h2o
```

**中文单词查询：**
```
https://www.bing.com/dict/search?q=%e6%b0%b4
```

---

## 六、地图搜索

### 基础 URL

```
https://www.bing.com/maps?q=地点
```

### 核心参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `q` | 地点搜索 | `q=北京` |
| `cp` | 中心点 | `cp=39.9~116.4` |
| `lvl` | 缩放级别 | `lvl=12` |

### 路线规划

```
https://www.bing.com/maps/directions?from=北京&to=上海
```

---

## 通用参数说明

### 分页参数

| 参数 | 说明 |
|------|------|
| `first` | 起始位置（从1开始） |
| `count` | 每页结果数量 |

### 会话参数（通常可忽略）

| 参数 | 说明 |
|------|------|
| `sid` | 会话 ID |
| `FORM` | 表单来源标识 |
| `qpvt` | 查询验证令牌 |

---

## URL 编码参考

### 常见字符编码

| 原字符 | 编码后 |
|--------|--------|
| 空格 | `+` 或 `%20` |
| 中文 | `%E4%B8%AD%E6%96%87` (UTF-8) |
| `"` | `%22` |

### URL 编码使用说明

中文关键词需要 URL 编码。使用内置工具（如 `fetch_url`）时，工具通常会自动处理编码。

**已编码的关键词示例：**
- `世界旅游胜地` → `%E4%B8%96%E7%95%8C%E6%97%85%E6%B8%B8%E8%83%9C%E5%9C%B0`
- `nature` → `nature`（无需编码）
