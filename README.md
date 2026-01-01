# 项目总结 - Simple Agents

## 📋 项目概述

Simple Agents 是一个基于 LangGraph 的智能 Agent 系统，支持文件操作、PDF 处理、多轮对话等功能。项目采用了模块化设计，提供了完整的测试套件和独立的测试运行器。

---

## 🎯 核心功能

### 1. 智能文件操作
- 列出文件和目录
- 创建、读取、编辑文件
- 支持多种文件格式（文本、Markdown、PDF 等）

### 2. PDF 处理
- PDF 转 Markdown 转换
- PDF 内容提取和分析
- 支持带文件上传的论文分析

### 3. 对话管理
- 多轮对话支持
- 上下文保持
- 独立会话隔离（基于 thread_id）

### 4. 沙箱环境
- 每个会话独立的文件系统沙箱
- 自动路径解析和隔离
- 支持虚拟模式

### 5. 工具系统
- 丰富的工具集合（文件、网络、转换等）
- 可扩展的工具中间件
- 工具调用限制和超时控制

---

## 📁 项目结构

```
simple-agents/
├── core/                          # 核心功能模块
│   ├── middleware/                 # 中间件（附件提取、路径解析等）
│   ├── tools/                     # 工具集合（PDF 转换、文件操作等）
│   └── utils/                     # 工具函数
├── deepagents/                    # Deep Agents 框架
│   ├── backends/                 # 后端实现（文件系统、内存等）
│   ├── middleware/               # Deep Agents 中间件
│   └── graph.py                 # Deep Agent 创建函数
├── tests/                        # 测试套件
│   ├── agents/                   # 独立测试运行器（可单独运行）
│   │   ├── output_handler.py   # 共享的输出处理模块
│   │   ├── run_*.py            # 8 个独立测试文件
│   │   ├── run_all.py          # 批量运行脚本
│   │   ├── README.md           # 详细文档
│   │   ├── QUICKSTART.md       # 快速开始指南
│   │   └── SETUP_SUMMARY.md   # 设置总结
│   ├── conftest.py            # pytest 配置（加载环境变量）
│   └── test_agent.py          # pytest 测试文件
├── files/                       # 测试文件
│   ├── 论文.pdf
│   └── 跟单宝.png
├── sandbox_sessions/             # 沙箱会话目录
├── graph.py                     # 主 Agent 配置
├── main.py                     # 主运行脚本
├── prompts.py                  # 系统提示词
├── .env                        # 环境变量配置
├── pyproject.toml              # 项目配置
└── README.md                   # 项目说明文档
```

---

## 🚀 快速开始

### 1. 启动服务器（可选）

```bash
# 启动 LangGraph 开发服务器
./start_server.sh

# 访问服务器
# http://localhost:2024
```

### 2. 环境配置

创建 `.env` 文件：

```bash
MODEL_MODEL_ID=your_model_id
MODEL_PROVIDER=anthropic
MODEL_BASE_URL=your_api_url
MODEL_API_KEY=your_api_key
```

### 2. 安装依赖

```bash
# 使用 pip
pip install -r requirements.txt

# 或使用 uv
uv sync
```

### 3. 运行测试

#### 独立测试运行器（推荐用于演示和调试）

```bash
# 运行单个测试
python tests/agents/run_simple_file_list.py
python tests/agents/run_pdf_to_markdown.py
python tests/agents/run_pdf_analysis.py
# ... 其他测试

# 运行所有测试
python tests/agents/run_all.py
```

#### pytest 测试（推荐用于自动化测试）

```bash
# 运行所有测试
pytest tests/test_agent.py -v

# 运行测试并显示详细输出
pytest tests/test_agent.py -s

# 运行特定测试
pytest tests/test_agent.py::TestAgent::test_simple_file_list -s
```

#### 主程序运行

```bash
# 单次对话
python main.py

# 多个独立对话（取消注释相关代码）
# asyncio.run(run_multiple_conversations(conversations))

# 交互式对话（取消注释相关代码）
# asyncio.run(run_with_user_input())
```

---

## 🖥️ 启动 LangGraph 服务器

### 快速启动

```bash
# 启动开发服务器
./start_server.sh

# 停止服务器
./stop_server.sh

# 访问服务器
# http://localhost:2024
```

### 服务器脚本

| 脚本 | 功能 |
|------|------|
| `start_server.sh` | 启动 LangGraph 开发服务器 |
| `stop_server.sh` | 停止运行中的服务器 |

### 常用命令

| 操作 | 命令 |
|------|------|
| 启动服务器 | `./start_server.sh` |
| 停止服务器 | `./stop_server.sh` |
| 查看进程 | `ps aux \| grep langgraph` |
| 查看端口 | `lsof -i :2024` |

---

## 📊 测试覆盖

| 测试场景 | pytest | 独立运行器 | 描述 |
|---------|--------|-------------|------|
| 简单的文件列表查询 | ✅ | ✅ | 查询根目录文件 |
| PDF 转 Markdown | ✅ | ✅ | PDF 文件格式转换 |
| PDF 论文分析 | ✅ | ✅ | 带文件上传的论文分析 |
| 多个独立对话 | ✅ | ✅ | 演示独立会话 |
| 多轮对话 | ✅ | ✅ | 演示上下文保持 |
| 工具调用 | ✅ | ✅ | 测试工具调用功能 |
| 错误处理 | ✅ | ✅ | 测试错误处理能力 |
| Markdown 文件操作 | ✅ | ✅ | 创建和读取 Markdown |

**总计：8 个测试场景，全部支持两种运行方式**

---

## 🎨 输出特性

### 实时流式输出

所有测试都支持实时流式输出，展示 AI 回复的打字机效果：

```
我来帮您列出根目录的文件。
```

### 工具调用详情

清晰显示工具调用的完整信息：

```
🔧 工具调用: ls
📥 参数:
{
  "path": "/"
}
✅ 工具 ls 执行完成
📤 结果: content='[]'
```

### AI 思考过程

显示模型的推理过程（如果有）：

```
💭 AI 思考过程:
用户想要列出根目录的文件，我需要使用 ls 工具...
```

### 测试框架

统一的测试开始和结束标识：

```
🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹
测试：简单的文件列表查询
🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹

[测试内容...]

✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅
简单的文件列表查询 完成
✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅✅
```

---

## 🔧 核心模块

### 1. 输出处理器（共享）

`tests/agents/output_handler.py` - 提供统一的流式输出处理

**主要函数：**
- `output_handler(event)` - 主事件处理器
- `print_header(title)` - 打印测试标题
- `print_user_message(message, attachments=None)` - 打印用户问题
- `print_footer(title=None)` - 打印测试完成标识

**特性：**
- 所有测试共享相同的输出格式
- 实时流式输出支持
- 详细的工具调用信息
- 统一的错误处理

### 2. Agent 配置

`graph.py` - 主 Agent 配置文件

**主要组件：**
- 模型配置（支持 Anthropic、OpenAI 等）
- 工具集合（文件、PDF、网络等）
- 中间件链（附件提取、路径解析、工具限制等）
- 子代理配置（研究代理）
- 后端工厂（会话隔离）

### 3. 中间件系统

**附件提取中间件** (`core/middleware/attachment_extract.py`)
- 提取消息中的文件附件
- 解析 base64 编码的文件
- 保存到沙箱环境

**路径解析中间件** (`core/middleware/tool_path_resolver.py`)
- 解析工具调用中的相对路径
- 转换为沙箱内的绝对路径
- 支持特定工具的路径处理

### 4. 工具系统

**文件操作工具**
- `ls` - 列出目录内容
- `read_file` - 读取文件
- `write_file` - 写入文件
- `edit_file` - 编辑文件
- `glob` - 文件匹配
- `grep` - 文本搜索

**PDF 处理工具**
- `convert_pdf_to_markdown` - PDF 转 Markdown

**网络工具**
- `fetch_markdown` - 获取网页内容并转换为 Markdown

**思考工具**
- `think_tool` - 思考和规划

---

## 🔄 运行方式对比

### pytest 测试 vs 独立测试运行器

| 特性 | pytest 测试 | 独立测试运行器 |
|------|-------------|----------------|
| **运行命令** | `pytest tests/test_agent.py` | `python tests/agents/run_xxx.py` |
| **依赖** | 需要安装 pytest | 纯 Python，无需额外依赖 |
| **输出** | 默认不显示，需 `-s` 参数 | 默认显示详细流式输出 |
| **断言** | 包含断言验证结果 | 仅展示功能，无断言 |
| **用途** | 自动化测试、CI/CD | 演示、调试、交互式测试 |
| **灵活性** | 固定测试流程 | 可自由修改和扩展 |
| **适合场景** | 回归测试、质量保证 | 功能演示、问题调试 |

### 推荐使用场景

**开发阶段：**
- 使用独立测试运行器进行快速调试
- 实时观察 agent 行为
- 快速验证新功能

**测试阶段：**
- 使用 pytest 进行自动化测试
- 验证功能正确性
- 确保代码质量

**演示阶段：**
- 使用独立测试运行器展示功能
- 流式输出提供良好的用户体验
- 可以交互式演示

---

## 📚 文档索引

### 项目文档
- `README.md` - 项目说明文档
- `PROJECT_SUMMARY.md` - 本文件（项目总结）

### 测试文档
- `tests/agents/README.md` - 独立测试运行器详细文档
- `tests/agents/QUICKSTART.md` - 快速开始指南
- `tests/agents/SETUP_SUMMARY.md` - 设置总结

---

## 💡 最佳实践

### 1. 添加新的独立测试

```bash
# 1. 复制现有测试文件
cp tests/agents/run_simple_file_list.py tests/agents/run_your_test.py

# 2. 编辑新文件
# - 修改测试描述
# - 修改用户消息
# - 调整 thread_id
# - 添加必要的逻辑

# 3. 更新文档
# - 在 tests/agents/README.md 中添加说明
# - 在 tests/agents/QUICKSTART.md 中添加快速开始链接
```

### 2. 调试技巧

- 使用独立测试运行器进行交互式调试
- 添加 `print()` 语句查看中间状态
- 调整 `tool_timeout` 参数（默认 30-300 秒）
- 使用 `thread_id` 隔离不同的测试会话

### 3. 性能优化

- 对于长时间运行的测试，增加 `tool_timeout`
- 使用 `thread_id` 隔离不同的测试会话
- 定期清理 `sandbox_sessions` 目录
- 考虑使用虚拟模式减少磁盘 I/O

---

## 🛠️ 故障排除

### 问题 1: 模块导入错误
```
ModuleNotFoundError: No module named 'graph'
```

**解决方案：** 确保在项目根目录下运行，或文件已添加项目根目录到 Python 路径。

### 问题 2: 环境变量未加载
```
Error: MODEL_MODEL_ID is not set
```

**解决方案：** 检查 `.env` 文件是否存在并包含所需的环境变量。

### 问题 3: 测试运行超时
```
TimeoutError: Tool execution timeout
```

**解决方案：** 增加 `config` 中的 `tool_timeout` 参数。

### 问题 4: pytest 测试失败
```
TypeError: _init_chat_model_helper() missing 1 required positional argument: 'model'
```

**解决方案：** 确保 `tests/conftest.py` 正确加载了环境变量。

---

## 🎉 项目亮点

### 1. 完整的测试体系
- 8 个测试场景，覆盖主要功能
- 支持 pytest 和独立运行两种方式
- 详细的输出和错误信息

### 2. 灵活的运行方式
- 可以作为独立脚本运行
- 可以作为 pytest 测试运行
- 支持批量运行所有测试

### 3. 优秀的用户体验
- 实时流式输出
- 清晰的测试框架
- 详细的工具调用信息

### 4. 模块化设计
- 共享的输出处理模块
- 统一的配置管理
- 可扩展的工具系统

### 5. 沙箱隔离
- 每个会话独立的文件系统
- 自动路径解析
- 安全的文件操作

---

## 🚀 立即开始

```bash
# 1. 运行第一个测试
python tests/agents/run_simple_file_list.py

# 2. 运行所有测试
python tests/agents/run_all.py

# 3. 查看文档
cat tests/agents/QUICKSTART.md
```

---

## 📄 许可证

本项目采用与主项目相同的许可证。

---

## 🤝 贡献

欢迎贡献代码、报告问题或提出建议！

---

**享受你的 Agent 测试之旅！** 🎊