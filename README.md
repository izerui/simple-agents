# Simple Agents - 项目说明

## 📋 项目概述

Simple Agents 是一个基于 LangGraph 的智能 Agent 系统，采用模块化设计，提供了完整的测试套件和独立的测试运行器。

---



## 🔧 环境配置

### 1. 创建环境变量文件

在项目根目录创建 `.env` 文件：

```bash
MODEL_MODEL_ID=your_model_id
MODEL_PROVIDER=anthropic
MODEL_BASE_URL=your_api_url
MODEL_API_KEY=your_api_key
```

### 2. 环境变量说明

| 变量 | 说明 | 示例 |
|------|------|------|
| `MODEL_MODEL_ID` | 模型 ID | `claude-3-5-sonnet-20241022` |
| `MODEL_PROVIDER` | 模型提供商 | `anthropic`, `openai` |
| `MODEL_BASE_URL` | API 基础 URL | `https://api.anthropic.com` |
| `MODEL_API_KEY` | API 密钥 | `sk-ant-xxxx` |

---

## 📦 安装依赖

### 使用 uv

```bash
uv sync
```

### 项目配置

项目的依赖和配置在 `pyproject.toml` 文件中定义：

```toml
[project]
name = "simple-agents"
version = "0.1.0"
dependencies = [
    # 依赖项列表
]
```

---

## 🚀 部署

### Docker 部署

使用 LangGraph CLI 生成 Dockerfile：

```bash
langgraph dockerfile --add-docker-compose -c langgraph.json ./Dockerfile
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