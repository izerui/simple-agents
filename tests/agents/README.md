# 项目结构总结 - Agent 独立测试运行器

## 📁 创建的文件结构

```
simple-agents/
├── tests/
│   ├── agents/                           # 新创建的独立测试运行器目录
│   │   ├── __init__.py                  # 包初始化文件
│   │   ├── output_handler.py            # 共享的事件输出处理器模块
│   │   ├── run_simple_file_list.py      # 简单的文件列表查询测试
│   │   ├── run_pdf_to_markdown.py      # PDF 转 Markdown 转换测试
│   │   ├── run_pdf_analysis.py         # 带文件上传的 PDF 论文分析测试
│   │   ├── run_multiple_conversations.py # 多个独立对话测试
│   │   ├── run_conversation_with_turns.py # 多轮对话测试
│   │   ├── run_tool_invocation.py      # 工具调用功能测试
│   │   ├── run_error_handling.py       # 错误处理测试
│   │   ├── run_markdown_file_operations.py # Markdown 文件操作测试
│   │   ├── run_interactive.py         # 交互式测试程序（可实时对话）
│   │   ├── run_all.py                 # 批量运行所有测试的脚本
│   │   ├── README.md                  # 详细文档
│   │   └── QUICKSTART.md              # 快速启动指南
│   ├── conftest.py                    # 新创建的 pytest 配置文件（加载环境变量）
│   └── test_agent.py                  # 原有的 pytest 测试文件（已优化）
├── graph.py                           # 主 Agent 配置文件
├── main.py                            # 主运行脚本
└── .env                              # 环境变量文件
```

---

## 🎯 主要改进

### 1. 创建了独立的测试运行器
所有测试都可以作为独立的 Python 脚本运行，无需 pytest。

### 2. 共享的输出处理模块
`tests/agents/output_handler.py` 提供统一的流式输出处理。

### 3. 修复了 pytest 环境变量问题
创建 `tests/conftest.py` 自动加载环境变量。

### 4. 优化了测试代码
使用通用的 fixture `run_agent_with_output`，减少代码重复。

---

## 🚀 快速开始

### 运行交互式测试

```bash
# 启动交互式测试（推荐用于调试和演示）
python tests/agents/run_interactive.py
```

**交互式测试特性：**
- 🎯 实时与 Agent 对话，无需每次修改代码
- 🔄 支持多轮对话，上下文自动保留
- 🛠️ 可以测试所有工具功能（文件操作、PDF 分析等）
- 💬 即时查看 AI 的流式回复
- 🚫 输入 'quit', 'exit', 'q' 或 Ctrl+C 退出

**使用场景：**
- 快速测试新的 Prompt 或功能
- 演示 Agent 能力给他人
- 调试复杂的多轮对话
- 探索 Agent 的工具调用行为

### 运行单个独立测试

```bash
# 简单的文件列表查询
python tests/agents/run_simple_file_list.py

# PDF 转 Markdown
python tests/agents/run_pdf_to_markdown.py

# PDF 论文分析（带文件上传）
python tests/agents/run_pdf_analysis.py

# 多个独立对话
python tests/agents/run_multiple_conversations.py

# 多轮对话
python tests/agents/run_conversation_with_turns.py

# 工具调用测试
python tests/agents/run_tool_invocation.py

# 错误处理测试
python tests/agents/run_error_handling.py

# Markdown 文件操作
python tests/agents/run_markdown_file_operations.py
```

### 运行所有独立测试

```bash
python tests/agents/run_all.py
```

### 运行 pytest 测试

```bash
# 运行所有 pytest 测试（无详细输出）
pytest tests/test_agent.py -v

# 运行 pytest 测试（显示详细输出）
pytest tests/test_agent.py -s
```

---

## 📦 核心文件说明

### 1. `tests/agents/output_handler.py` - 共享模块

这是所有独立测试运行器的核心模块，提供：

**函数列表：**
- `output_handler(event)` - 主事件处理器
  - 实时流式输出 AI 回复（打字机效果）
  - 显示工具调用及参数
  - 显示工具执行结果
  - 显示错误信息

- `print_header(title)` - 打印测试标题
- `print_user_message(message, attachments=None)` - 打印用户问题和附件
- `print_footer(title=None)` - 打印测试完成标识

**特性：**
- 所有测试共享相同的输出格式
- 统一的代码风格
- 易于维护和扩展

### 2. `tests/conftest.py` - pytest 配置

自动加载环境变量，确保 pytest 测试能正常运行。

```python
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
project_root = Path(__file__).parent.parent
load_dotenv(dotenv_path=project_root / '.env', verbose=True)
```

### 4. 交互式测试程序

`tests/agents/run_interactive.py` 提供了一个完全交互式的测试环境：

```python
class InteractiveAgent:
    """交互式Agent会话管理器"""
    
    def __init__(self):
        self.thread_id = "interactive_session_" + ...
        self.running = True
        self.config = RunnableConfig(...)
    
    async def process_message(self, user_message: str):
        """处理用户消息"""
        # 实时显示用户问题和 AI 回复
        # 支持流式输出和工具调用
    
    async def run(self):
        """运行交互式会话"""
        while self.running:
            user_input = input("👤 你: ")
            if self.should_exit(user_input):
                break
            await self.process_message(user_input)
```

**运行方式：**
```bash
python tests/agents/run_interactive.py
```

**使用示例：**
```
👤 你: 列出当前目录的文件
🤖 AI: 我来帮您列出当前目录的文件...[流式输出]

👤 你: 创建一个 test.md 文件
🤖 AI: 好的，我来为您创建这个文件...[工具调用]

👤 你: 读取 test.md 的内容
🤖 AI: 文件内容如下...[显示结果]

👤 你: quit
👋 再见！
```

### 5. 独立测试运行器

每个独立测试运行器都遵循相同的模式：

```python
import asyncio
from pathlib import Path
import sys
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

# 加载环境变量并添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
load_dotenv(dotenv_path=project_root / '.env')

from graph import agent
from tests.agents.output_handler import output_handler, print_header, print_user_message, print_footer

async def run_test():
    """运行测试"""
    # 打印测试标题
    print_header("测试标题")
    
    # 显示用户问题
    print_user_message(user_message)
    
    # 创建 inputs 和 config
    inputs = {"messages": [HumanMessage(content=user_message)]}
    config = RunnableConfig(...)
    
    # 执行 agent（流式输出）
    async for event in agent.astream_events(inputs, version="v2", config=config):
        output_handler(event)
    
    # 打印测试完成标识
    print_footer("测试标题")

if __name__ == "__main__":
    asyncio.run(run_test())
```

---

## 🔄 与 pytest 测试的关系

| 特性 | pytest 测试 | 交互式测试 | 独立测试运行器 |
|------|-------------|-------------|----------------|
| **文件位置** | `tests/test_agent.py` | `tests/agents/run_interactive.py` | `tests/agents/run_*.py` |
| **运行方式** | `pytest tests/test_agent.py` | `python tests/agents/run_interactive.py` | `python tests/agents/run_xxx.py` |
| **输出** | 默认不显示输出，需 `-s` 参数 | 实时交互，支持多轮对话 | 默认显示详细流式输出 |
| **断言** | 包含断言验证结果 | 仅展示功能，无断言 | 仅展示功能，无断言 |
| **用途** | 自动化测试、CI/CD | 实时对话、探索、演示 | 演示、调试、自动化测试 |
| **环境变量** | 通过 `conftest.py` 加载 | 文件内加载 | 每个文件独立加载 |
| **独立性** | 需要安装 pytest | 纯 Python，无需额外依赖 | 纯 Python，无需额外依赖 |

### 三者如何协作

1. **共享输出逻辑** - 所有测试都使用 `tests/agents/output_handler.py`
2. **统一环境配置** - 都使用 `conftest.py` 或文件内的环境变量加载
3. **互补功能** - pytest 用于自动化测试，交互式测试用于实时探索，独立运行器用于演示和调试

---

## 💡 使用建议

### 开发阶段
- 使用**独立测试运行器**进行快速调试和演示
- 实时看到流式输出，便于观察 agent 行为

### 测试阶段
- 使用 **pytest** 进行自动化测试
- 验证功能正确性，确保代码质量

### 部署阶段
- 使用 `run_all.py` 运行所有独立测试，确保功能完整
- 使用 pytest 进行回归测试

---

## 📚 文档索引

- **详细文档**: `tests/agents/README.md`
- **快速开始**: `tests/agents/QUICKSTART.md`
- **本总结**: `tests/agents/SETUP_SUMMARY.md`

---

## ✨ 输出特性

所有测试（pytest 和独立运行器）都支持：

### 1. 实时流式输出
```
我来帮您列出根目录的文件。  ← 逐字显示（打字机效果）
```

### 2. 工具调用详情
```
🔧 工具调用: ls
📥 参数:
{
  "path": "/"
}
✅ 工具 ls 执行完成
📤 结果: content='[]'
```

### 3. 测试框架
```
🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹
测试：简单的文件列表查询
🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹🔹
```

---

## 🎓 最佳实践

### 1. 添加新的独立测试

```bash
# 1. 创建新的测试文件
cp tests/agents/run_simple_file_list.py tests/agents/run_your_test.py

# 2. 编辑新文件
# - 修改测试描述
# - 修改用户消息
# - 调整 thread_id
# - 添加必要的逻辑

# 3. 更新文档
# - 在 README.md 中添加说明
# - 在 QUICKSTART.md 中添加快速开始链接
```

### 2. 调试技巧

- 使用独立测试运行器进行交互式调试
- 添加 `print()` 语句查看中间状态
- 调整 `tool_timeout` 参数（默认 30-300 秒）

### 3. 性能优化

- 对于长时间运行的测试，增加 `tool_timeout`
- 使用 `thread_id` 隔离不同的测试会话
- 定期清理 `./data/sandbox_sessions` 目录

---

## 🔧 故障排除

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

---

## 📈 测试覆盖

| 测试场景 | pytest | 独立运行器 |
|---------|--------|-------------|
| 文件列表查询 | ✅ | ✅ |
| PDF 转 Markdown | ✅ | ✅ |
| PDF 论文分析 | ✅ | ✅ |
| 多个独立对话 | ✅ | ✅ |
| 多轮对话 | ✅ | ✅ |
| 工具调用 | ✅ | ✅ |
| 错误处理 | ✅ | ✅ |
| Markdown 文件操作 | ✅ | ✅ |

**总计：8 个测试场景，全部支持两种运行方式**

---

## 🎉 总结

这个项目现在拥有：

1. ✅ **完整的 pytest 测试套件** - 用于自动化测试和 CI/CD
2. ✅ **8 个独立测试运行器** - 用于演示、调试和交互式测试
3. ✅ **统一的输出处理模块** - 确保一致的输出格式
4. ✅ **详细的使用文档** - README、QUICKSTART、SETUP_SUMMARY
5. ✅ **批量运行脚本** - 一键运行所有独立测试
6. ✅ **流式输出支持** - 所有测试都支持实时输出
7. ✅ **环境变量自动加载** - 修复了 pytest 的环境变量问题

---

## 🚀 立即开始

```bash
# 启动交互式测试（推荐）
python tests/agents/run_interactive.py

# 运行第一个测试
python tests/agents/run_simple_file_list.py

# 运行所有测试
python tests/agents/run_all.py

# 查看快速开始指南
cat tests/agents/QUICKSTART.md
```

**享受你的 Agent 测试之旅！** 🎊