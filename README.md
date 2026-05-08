# Simple Agents - 智能代理系统

## 🎯 项目定位

Simple Agents 是一个**企业级智能代理框架**，基于 LangGraph 构建，提供开箱即用的 AI Agent 能力。适用于需要复杂任务编排、多模态处理和安全隔离的场景。

### 核心特点

- **🔧 模块化架构** - 中间件、技能、工具完全解耦，易于扩展
- **🔒 安全隔离** - 每个对话独立沙箱环境（`data/sandbox_sessions/{thread_id}/`）
- **🤖 子代理支持** - 内置研究子代理，支持任务委托和并行执行
- **📊 多模态处理** - 支持 PDF、Excel、Word、图片等文件处理
- **🌐 Web 研究能力** - 智能网页抓取、内容提取和 Markdown 转换
- **💾 持久化存储** - Redis + PostgreSQL，支持对话历史和状态管理
- **🔄 动态模型切换** - 运行时切换 LLM 模型（Anthropic/OpenAI/DeepSeek）
- **🎨 完整 UI** - 配套 Web 聊天界面（agent-chat-ui）

---

## 🏗️ 系统架构

### 核心组件

```
simple-agents/
├── src/
│   ├── graph.py              # 主 Agent 定义（LangGraph 入口）
│   ├── webapp.py             # FastAPI 服务（文件下载、模型列表）
│   ├── middleware/           # 中间件层
│   │   ├── attachment_extract.py       # 附件提取
│   │   ├── streaming_tool_call_fix.py  # 流式输出修复
│   │   ├── generated_files.py          # 生成文件追踪
│   │   └── suggested_questions.py      # 建议问题生成
│   ├── skills/               # 技能模块（可插拔）
│   │   ├── pdf/              # PDF 处理（填充、转图片）
│   │   ├── xlsx/             # Excel 处理（重算、分析）
│   │   ├── pandas-data-analysis/  # 数据分析
│   │   ├── relation-graph/   # 关系图谱构建
│   │   └── tavily-search/    # 搜索增强
│   ├── tools/                # 基础工具
│   │   ├── think.py          # 思考工具（推理链）
│   │   ├── fetch.py          # URL 抓取
│   │   └── converts.py       # 格式转换
│   └── prompts.py            # 提示词管理
├── deepagents/               # 核心框架包
│   ├── graph.py              # create_deep_agent 主函数
│   ├── middleware/           # 框架中间件
│   │   ├── filesystem.py     # 文件系统操作
│   │   ├── memory.py         # 记忆管理
│   │   ├── subagents.py      # 子代理调度
│   │   ├── skills.py         # 技能加载
│   │   └── summarization.py  # 上下文压缩
│   └── backends/             # 后端实现
│       ├── sandbox.py        # 沙箱隔离
│       ├── filesystem.py     # 文件操作
│       └── store.py          # 存储抽象
└── docker-compose.yml        # 多服务编排
```

### 服务架构

```
┌─────────────────┐
│  agent-chat-ui  │  (端口 8124)
│   Web 聊天界面  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   agents-api    │  (端口 8123)
│  LangGraph 服务 │
└────┬───┬───┬────┘
     │   │   │
     │   │   └──────────┐
     │   │              ▼
     │   │      ┌───────────────┐
     │   │      │browser-service│ (端口 2025)
     │   │      │  浏览器抓取   │
     │   │      └───────────────┘
     │   │
     ▼   ▼
┌─────┐ ┌──────────┐
│Redis│ │PostgreSQL│ (端口 5433)
└─────┘ └──────────┘
```

---

## 🚀 核心功能

### 1. 智能对话与推理

- **思考链（Chain of Thought）** - `think_tool` 支持复杂推理
- **上下文管理** - 自动压缩长对话，保持关键信息
- **流式输出** - 实时响应，优化用户体验

### 2. Web 研究能力

- **智能抓取** - 通过 `browser-service` 渲染 JavaScript 页面
- **内容提取** - 自动转换为 Markdown 格式
- **研究子代理** - 专门处理深度研究任务（限制 500 次工具调用）

### 3. 文件处理

| 文件类型 | 支持操作 |
|---------|---------|
| **PDF** | 填充表单、转图片、提取文本 |
| **Excel** | 公式重算、数据分析、图表生成 |
| **Word** | 内容提取、格式转换 |
| **图片** | OCR、视觉理解 |

### 4. 数据分析

- **Pandas 集成** - 自动生成数据分析代码
- **SQL 分析** - 支持数据库查询和可视化
- **关系图谱** - 构建实体关系网络

### 5. 安全与隔离

- **沙箱环境** - 每个对话独立文件系统
- **工具限制** - 防止无限循环（全局 500 次，单工具可配置）
- **API 认证** - 基于 API Key 的访问控制

### 6. 扩展性

- **中间件机制** - 请求/响应拦截和修改
- **技能插件** - 从 `/skills` 目录自动加载
- **动态工具** - 运行时注入工具（`config.configurable.dynamic_tools`）
- **模型切换** - 支持多种 LLM 提供商

---

## 📊 技术栈

| 层级 | 技术 |
|------|------|
| **框架** | LangGraph 1.0.9, LangChain 1.2.11 |
| **LLM** | Anthropic Claude, OpenAI, DeepSeek |
| **后端** | FastAPI 0.132.0, Python 3.12+ |
| **存储** | Redis 6, PostgreSQL 16 (pgvector) |
| **前端** | agent-chat-ui (React) |
| **容器** | Docker Compose |
| **数据处理** | Pandas 3.0.1, openpyxl 3.1.5 |

---

## 🎯 适用场景

### 通用场景

1. **智能客服** - 多轮对话、知识库检索
2. **内容创作** - 文章生成、文档处理
3. **数据分析** - 自动化报表、可视化
4. **研究助手** - Web 搜索、信息整合

### 垂直领域

1. **金融分析** - 财报解读、市场研究
2. **法律咨询** - 文档审查、案例检索
3. **教育培训** - 作业批改、教学设计
4. **电商运营** - 商品分析、用户画像

---

## 🔧 快速开始

### 1. 环境配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件
L_MODEL_MODEL_ID=claude-3-5-sonnet-20241022
L_MODEL_PROVIDER=anthropic
L_MODEL_API_KEY=sk-ant-xxxx
```

### 2. 安装依赖

```bash
uv sync
```

### 3. 启动服务

```bash
# 开发模式（单机）
./start_server.sh

# 生产模式（Docker Compose）
docker-compose up -d
```

### 4. 访问服务

- **API 服务**: http://localhost:8123
- **Web 界面**: http://localhost:8124
- **浏览器服务**: http://localhost:2025

---

## 💡 核心优势

### vs 传统 Chatbot

| 特性 | Simple Agents | 传统 Chatbot |
|------|--------------|-------------|
| 任务编排 | ✅ 多步骤自动化 | ❌ 单轮问答 |
| 文件处理 | ✅ 多格式支持 | ❌ 仅文本 |
| 代码执行 | ✅ 沙箱隔离 | ❌ 不支持 |
| 子任务委托 | ✅ 子代理机制 | ❌ 单一流程 |

### vs 其他 Agent 框架

| 特性 | Simple Agents | AutoGPT | LangChain |
|------|--------------|---------|-----------|
| 生产就绪 | ✅ 完整部署方案 | ❌ 实验性 | ⚠️ 需自行集成 |
| 安全隔离 | ✅ 内置沙箱 | ❌ 无隔离 | ⚠️ 需自行实现 |
| UI 界面 | ✅ 开箱即用 | ❌ 无 | ❌ 无 |
| 中间件 | ✅ 完整生态 | ❌ 有限 | ⚠️ 需自行开发 |

---

## 🛣️ 商业化路径

### 1. SaaS 服务

- **按量计费** - API 调用次数、Token 消耗
- **订阅制** - 企业版、专业版、基础版
- **私有部署** - 一次性授权费 + 年度维护

### 2. 垂直解决方案

- **行业定制** - 金融/法律/教育专用版
- **集成服务** - 与企业现有系统对接
- **咨询培训** - Agent 开发培训、最佳实践

### 3. 技术授权

- **白标方案** - 品牌定制、源码授权
- **插件市场** - 技能/中间件付费生态
- **技术支持** - 企业级 SLA 保障

---

## 📈 性能指标

- **响应延迟**: < 2s (首 Token)
- **并发支持**: 100+ 对话/实例
- **文件处理**: 支持 100MB+ 文档
- **沙箱隔离**: 完全独立，无交叉污染
- **工具调用**: 500 次/对话（可配置）

---

## 🔗 相关资源

- **文档**: [LangGraph Docs](https://docs.langchain.com/langsmith/monorepo-support)
- **部署**: [Helm Charts](https://github.com/langchain-ai/helm)
- **认证**: [API Auth Guide](https://docs.langchain.com/langsmith/custom-auth)
- **技能开发**: [Skills Documentation](https://docs.langchain.com/oss/python/langchain/multi-agent/skills)

---

## 📝 版本信息

- **当前版本**: v0.2.0
- **Python 要求**: >= 3.12
- **LangGraph**: 1.0.9
- **更新日期**: 2026-04-29

---

## 🤝 支持与反馈

如需技术支持或商务合作，请联系项目维护者。
