# Simple Agents - 项目说明

## 📋 项目概述

Simple Agents 是一个基于 LangGraph 的智能 Agent 系统，采用模块化设计，提供了完整的测试套件和独立的测试运行器。

---



## 🔧 环境配置

### 1. 创建环境变量文件

在项目根目录创建 `.env` 文件：

```bash
L_MODEL_MODEL_ID=your_model_id
L_MODEL_PROVIDER=anthropic
L_MODEL_BASE_URL=your_api_url
L_MODEL_API_KEY=your_api_key
```

### 2. 环境变量说明

| 变量 | 说明 | 示例 |
|------|------|------|
| `L_MODEL_MODEL_ID` | 模型 ID | `claude-3-5-sonnet-20241022` |
| `L_MODEL_PROVIDER` | 模型提供商 | `anthropic`, `openai` |
| `L_MODEL_BASE_URL` | API 基础 URL | `https://api.anthropic.com` |
| `L_MODEL_API_KEY` | API 密钥 | `sk-ant-xxxx` |

---

## 📦 安装依赖

### 使用 uv

```bash
uv sync
```

## 🚀 部署

### 生成Dockerfile
```
langgraph dockerfile -c langgraph.json Dockerfile
```

### Docker 部署

使用 LangGraph CLI 生成 Dockerfile：

```bash
langgraph dockerfile -c langgraph.json Dockerfile
```

### 启动 LangGraph 服务器

#### 快速启动

```bash
# 启动开发服务器
./start_server.sh

# 停止服务器
./stop_server.sh

# 访问服务器
# http://localhost:2024
```


参考文档:
1. [LangGraph](https://docs.langchain.com/langsmith/monorepo-support#langgraph-json-configuration)
2. [LangGraph Command](https://docs.langchain.com/langsmith/cli#dockerfile)
3. [Helm](https://github.com/langchain-ai/helm)
4. [Custom Docker](https://docs.langchain.com/langsmith/custom-docker)
5. [Api Auth](https://docs.langchain.com/langsmith/custom-auth)
5. [skill](https://docs.langchain.com/oss/python/langchain/multi-agent/skills)
