# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Simple Agents 是一个基于 LangGraph 的智能 Agent 系统，采用模块化设计，提供 Web 研究、文件处理等能力。

## Commands

### Environment Setup
```bash
uv sync                    # 安装依赖（使用 pyproject.toml）
```

### Development Server
```bash
./start_server.sh         # 启动 LangGraph 开发服务器 (localhost:2024)
./stop_server.sh          # 停止服务器
```

### Deployment
```bash
langgraph dockerfile -c langgraph.json Dockerfile  # 生成 Dockerfile
```

### Testing
```bash
pytest tests/                           # 运行所有测试
pytest tests/agents/run_*.py            # 运行特定 agent 测试
pytest tests/clients/test_*.py          # 运行客户端测试
pytest tests/test_sandbox/              # 运行沙箱相关测试
```

## Architecture

### Core Structure
- `src/graph.py` - 主 Agent 定义，使用 `create_deep_agent` 创建
- `src/webapp.py` - FastAPI 应用，提供文件下载和模型列表接口
- `deepagents/` - 核心 Agent 框架包

### Key Modules
- `deepagents/graph.py` - `create_deep_agent` 主函数，创建 LangGraph Agent
- `deepagents/middleware/` - 中间件：filesystem, memory, subagents, summarization, skills
- `deepagents/backends/` - 后端实现：sandbox, filesystem, store, composite
- `src/middleware/` - 工具类中间件：streaming_tool_call_fix, attachment_extract, generated_files
- `src/skills/` - 技能实现：pdf, docx, xlsx, pandas-data-analysis, sql-analytics, skill-creator
- `src/tools/` - 工具：think, fetch, converts
- `src/prompts.py` - 提示词管理，从 prompt/ 目录加载

### Configuration Files
- `langgraph.json` - LangGraph 配置，定义入口为 `src/graph.py:agent`
- `pyproject.toml` - Python 项目配置，依赖管理
- `docker-compose.yml` - 多服务部署：redis, postgres, agents-api, agent-chat-ui, browser-service
- `.env` - 环境变量配置（参考 `.env.example`）

### Environment Variables
主要配置项：
- `L_MODEL_MODEL_ID` - 模型 ID
- `L_MODEL_PROVIDER` - 模型提供商 (anthropic, openai, deepseek 等)
- `L_MODEL_BASE_URL` - API 基础 URL
- `L_MODEL_API_KEY` - API 密钥
- `REDIS_URI` / `DATABASE_URI` - Redis 和 PostgreSQL 连接
- `BROWSER_SERVICE_URL` - 浏览器抓取服务地址

### Data Directories
- `data/sandbox_sessions/{thread_id}/` - 每个对话的隔离沙箱目录
- `data/postgres/` - PostgreSQL 数据目录

## Testing Patterns

测试文件位于 `tests/` 目录：
- `tests/agents/` - Agent 集成测试，包含 run_*.py 脚本
- `tests/clients/` - API 客户端测试
- `tests/test_sandbox/` - 沙箱安全隔离测试

运行单个测试：
```bash
python tests/agents/run_simple_url_fetch.py
```
