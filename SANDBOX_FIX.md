# 沙箱隔离功能使用指南

本文档说明了如何使用 `deepagents` 实现每个对话独立的沙箱路径，并在对话结束后自动清理。

## 🔧 核心原理

### 关键发现

通过调试发现，`Runtime.config` 的结构如下：

```python
config = {
    'configurable': {
        'thread_id': 'abc123-def456...',  # ← 在这里！
    },
    'metadata': {
        'thread_id': 'abc123-def456...',  # ← 也可以从这里获取
    },
    'recursion_limit': 100,
    # ... 其他配置
}
```

**重要：** `thread_id` 不在 `config['thread_id']`，而在 `config['configurable']['thread_id']`！

### BackendFactory 的工作方式

`BackendFactory` 是一个函数，接受 `ToolRuntime` 对象并返回 `BackendProtocol`：

```python
def backend_factory(runtime: ToolRuntime) -> BackendProtocol:
    # 从 runtime.config 中获取 thread_id
    thread_id = runtime.config['configurable'].get('thread_id')
    
    # 创建独立的沙箱目录
    session_dir = sandbox_sessions / f"session_{thread_id[:8]}"
    
    # 返回配置好的 backend
    return FilesystemBackend(root_dir=str(session_dir), virtual_mode=True)
```

## 📁 文件结构

```
simple-agents/
├── deepagents/
│   └── sandbox_backend.py    # 沙箱管理器
├── analysis.py                  # Agent 配置（已修改）
├── main.py                     # 运行脚本（已修改）
├── sandbox_sessions/             # 沙箱目录（自动创建）
│   ├── session_abc12345/       # 对话 A 的沙箱
│   │   ├── deepagent_request.md
│   │   └── final_report.md
│   ├── session_def67890/       # 对话 B 的沙箱
│   │   └── ...
│   └── session_ghi12345/       # 对话 C 的沙箱
│       └── ...
└── SANDBOX_FIX.md             # 本文档
```

## 🚀 使用方式

### 1. 基本使用（单次对话）

```python
import asyncio
import uuid
from analysis import agent
from langchain_core.messages import HumanMessage

async def main():
    # 生成唯一的 thread_id
    thread_id = str(uuid.uuid4())
    
    # ✅ 关键：thread_id 必须在 configurable 中
    config = {
        "configurable": {"thread_id": thread_id},  # ← 这里！
        "recursion_limit": 100
    }
    
    try:
        # 运行 agent
        result = await agent.ainvoke(
            {"messages": [HumanMessage("你的消息")]},
            config=config
        )
    finally:
        # 清理沙箱
        from sandbox_backend import sandbox_manager
        sandbox_manager.cleanup_session(thread_id)

asyncio.run(main())
```

### 2. 使用 main.py 运行

```bash
# 默认运行（使用默认消息）
python3 main.py

# 自定义消息
python3 main.py "请帮我分析 help.md 文件"

# 多个独立对话演示
python3 main.py multiple

# 交互式对话
python3 main.py interactive
```

### 3. 并发对话（每个独立沙箱）

```python
import asyncio
import uuid
from analysis import agent
from langchain_core.messages import HumanMessage
from sandbox_backend import sandbox_manager

async def run_conversation(message: str):
    thread_id = str(uuid.uuid4())
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 100
    }
    
    try:
        await agent.ainvoke(
            {"messages": [HumanMessage(message)]},
            config=config
        )
    finally:
        sandbox_manager.cleanup_session(thread_id)

# 并发运行多个对话
tasks = [
    run_conversation("任务 1"),
    run_conversation("任务 2"),
    run_conversation("任务 3"),
]
await asyncio.gather(*tasks)
```

### 4. 连续对话（同一会话，共享沙箱）

```python
import uuid
from analysis import agent
from langchain_core.messages import HumanMessage

# 使用同一个 thread_id
thread_id = str(uuid.uuid4())
config = {
    "configurable": {"thread_id": thread_id},
    "recursion_limit": 100
}

# 第一轮对话
await agent.ainvoke(
    {"messages": [HumanMessage("创建一个文件 test.md")]},
    config=config
)

# 第二轮对话（可以访问之前创建的 test.md）
await agent.ainvoke(
    {"messages": [HumanMessage("读取 test.md 的内容")]},
    config=config
)

# 第三轮对话
await agent.ainvoke(
    {"messages": [HumanMessage("修改 test.md 的内容")]},
    config=config
)

# 结束后清理
from sandbox_backend import sandbox_manager
sandbox_manager.cleanup_session(thread_id)
```

## 📊 核心代码说明

### sandbox_backend.py

```python
class SandboxBackendManager:
    def create_backend_factory(self) -> BackendFactory:
        def backend_factory(runtime: ToolRuntime) -> BackendProtocol:
            # 获取 thread_id
            config = runtime.config
            thread_id = None
            
            # 方式 1: 从 configurable 获取（推荐）
            if isinstance(config, dict):
                if 'configurable' in config:
                    thread_id = config['configurable'].get('thread_id')
                
                # 方式 2: 从 metadata 获取（备用）
                if thread_id is None and 'metadata' in config:
                    thread_id = config['metadata'].get('thread_id')
            
            # 如果还是没有，生成新的 UUID 作为后备
            if thread_id is None:
                thread_id = str(uuid.uuid4())
            
            # 创建沙箱目录
            session_dir = self.create_session_dir(thread_id)
            
            return FilesystemBackend(
                root_dir=str(session_dir),
                virtual_mode=True
            )
        
        return backend_factory
```

### analysis.py

```python
from sandbox_backend import sandbox_manager

# ✅ 使用 BackendFactory，而不是固定的 backend
agent = create_deep_agent(
    model=model,
    tools=[think_tool],
    system_prompt=INSTRUCTIONS,
    backend=sandbox_manager.create_backend_factory(),  # ← 关键！
    subagents=[research_sub_agent],
)
```

### main.py

```python
async def run_agent_with_cleanup(user_message: str = None):
    thread_id = str(uuid.uuid4())
    
    # ✅ 关键：thread_id 必须在 configurable 中
    config = {
        "configurable": {"thread_id": thread_id},  # ← 正确方式
        "recursion_limit": 100
    }
    
    try:
        await agent.ainvoke(inputs, config=config)
    finally:
        sandbox_manager.cleanup_session(thread_id)
```

## ⚠️ 常见错误

### 错误 1: 直接在 config 中传递 thread_id

```python
# ❌ 错误
config = {
    "thread_id": thread_id,  # × 不会工作！
}

# ✅ 正确
config = {
    "configurable": {"thread_id": thread_id},  # ✓ 正确
}
```

### 错误 2: 忘记清理沙箱

```python
# ❌ 错误：没有清理
await agent.ainvoke(...)

# ✅ 正确：使用 finally 确保清理
try:
    await agent.ainvoke(...)
finally:
    sandbox_manager.cleanup_session(thread_id)
```

### 错误 3: 每次调用都使用新的 thread_id

```python
# ❌ 错误：每次都生成新的 ID（无法共享文件）
for i in range(3):
    thread_id = str(uuid.uuid4())  # × 每次都是新的
    await agent.ainvoke(..., config={...})

# ✅ 正确：使用相同的 ID（可以共享文件）
thread_id = str(uuid.uuid4())
for i in range(3):
    await agent.ainvoke(..., config={"configurable": {"thread_id": thread_id}})
```

## 🔍 调试技巧

### 查看 runtime 的结构

如果需要调试，可以在 `sandbox_backend.py` 中添加：

```python
def backend_factory(runtime: ToolRuntime) -> BackendProtocol:
    # 调试信息
    print(f"runtime 类型: {type(runtime)}")
    print(f"config 内容: {runtime.config}")
    
    thread_id = runtime.config['configurable'].get('thread_id')
    # ...
```

### 查看沙箱内容

```python
from sandbox_backend import sandbox_manager
from pathlib import Path

# 查看会话信息
session_info = sandbox_manager.get_session_info(thread_id)
print(f"沙箱目录: {session_info['session_dir']}")
print(f"文件数量: {session_info['file_count']}")

# 列出所有文件
session_dir = Path(session_info['session_dir'])
for file_path in session_dir.rglob("*"):
    if file_path.is_file():
        print(f"  - {file_path.relative_to(session_dir)}")
```

## 🎯 最佳实践

1. **始终清理沙箱**：使用 `try-finally` 确保即使发生异常也会清理
2. **使用唯一的 thread_id**：每个对话使用 UUID 生成唯一的 ID
3. **在 configurable 中传递**：`config={"configurable": {"thread_id": thread_id}}`
4. **监控沙箱使用**：定期检查 `sandbox_sessions/` 目录大小
5. **定期清理遗留沙箱**：实现定时任务清理过期的沙箱目录

## 📝 总结

✅ **核心要点：**
- 使用 `BackendFactory` 动态创建 backend
- 在 `config['configurable']['thread_id']` 中传递 thread_id
- 对话结束后调用 `cleanup_session(thread_id)` 清理
- 每个对话获得独立的文件系统，互不干扰

✅ **测试验证：**
```bash
# 运行测试
python3 main.py "请创建一个测试文件"

# 检查沙箱目录
ls -la sandbox_sessions/

# 清理后应该看到
# 🗑️  清理沙箱目录: sandbox_sessions/session_xxxxxxxx
```

现在你可以放心地使用沙箱隔离功能了！每个对话都有自己独立的文件系统，不会互相干扰。