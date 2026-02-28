# LangGraph 流式输出详解

本文档详细描述 LangGraph 流式输出的整体架构、事件类型、数据结构以及各种消息类型的处理方式。

---

## 一、整体架构

### 1.1 请求流程概览

```
客户端请求                    LangGraph Server                   LLM/工具
    │                           │                               │
    │──── POST /runs/stream ──>│                               │
    │                           │──── model.invoke() ───────>│
    │                           │<─── 流式响应 ──────────────│
    │<─── Stream Events ───────│                               │
    │                           │                               │
    │                           │──── Tool Execution ────────>│
    │                           │<─── Tool Result ────────────│
    │<─── Stream Events ───────│                               │
    │                           │                               │
```

### 1.2 流式事件序列

一次完整的 LangGraph 流式输出会经历以下阶段：

```
┌─────────────────────────────────────────────────────────────────────┐
│                         LangGraph 流式事件序列                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. 初始请求                                                        │
│     └── metadata 事件（run_id, attempt）                             │
│                                                                      │
│  2. LLM 处理阶段                                                    │
│     ├── messages 事件（system 消息）                                │
│     ├── messages 事件（human 消息 - 用户输入）                       │
│     ├── messages 事件（AIMessageChunk - 文本流式输出）                │
│     ├── messages 事件（AIMessageChunk - 工具调用开始）                 │
│     ├── messages 事件（AIMessageChunk - 工具参数流式）                │
│     └── messages 事件（AIMessageChunk - 结束标记）                    │
│                                                                      │
│  3. 工具执行阶段（如果 LLM 决定调用工具）                             │
│     └── messages 事件（tool - 工具执行结果）                          │
│                                                                      │
│  4. 自定义事件（可选）                                               │
│     └── custom 事件（generated_files 等）                            │
│                                                                      │
│  5. 完成                                                             │
│     └── metadata 事件（完成标记）                                    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 核心概念

| 概念 | 说明 |
|------|------|
| Stream | LangGraph 提供的流式输出接口 |
| StreamPart | 流式返回的单个事件对象 |
| messages | 主要消息事件，包含各种类型的消息内容 |
| custom | 自定义事件，用于传输额外信息 |
| AIMessageChunk | AI 消息块，LLM 流式输出的载体 |
| ToolMessage | 工具执行结果消息 |
| tool_call_id | 工具调用唯一标识，用于关联调用和结果 |

---

## 二、Stream Mode 配置

```python
stream_mode=["messages-tuple", "custom"]
```

| 模式 | 说明 |
|------|------|
| `messages-tuple` | 以元组 `(event_name, data)` 形式返回消息事件 |
| `messages` | 返回消息事件（对象格式） |
| `values` | 返回图的当前状态值 |
| `custom` | 自定义事件（如 generated_files） |
| `updates` | 图节点更新 |

### 返回格式对比

**messages-tuple 模式**:
```python
chunk.event  # "messages"
chunk.data   # [msg_list, metadata]
```

**messages 模式**:
```python
chunk.event  # "messages"
chunk.data   # {"messages": [...], ...}
```

---

## 三、事件类型概览

| 事件名 | 说明 | 出现阶段 |
|--------|------|----------|
| `metadata` | 元数据事件 | 开头/结尾 |
| `messages` | 消息事件 | 全程 |
| `custom` | 自定义事件 | 任意时刻 |
| `values` | 状态值事件 | 任意时刻 |

### 消息类型分类

| 类型 | 说明 | 出现场景 |
|------|------|----------|
| `AIMessageChunk` | AI 消息块 | LLM 流式输出 |
| `tool` | 工具执行结果 | 工具执行后 |
| `tool_call` | 工具调用请求 | 决定调用工具时 |
| `tool_call_chunk` | 工具参数块 | 参数流式传输 |
| `system` | 系统消息 | 对话开始 |
| `human` | 用户消息 | 用户输入 |
| `text` | 文本块 | 文本内容 |

---

## 四、消息处理流程

```
┌─────────────────────────────────────────────────────────────────┐
│                     消息处理流程图                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  async for chunk in client.runs.stream(...):                    │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ 1. 判断 chunk 类型                                        │    │
│  │    chunk.event ∈ {messages, custom, metadata, values} │    │
│  └─────────────────────────────────────────────────────────┘    │
│       │                                                          │
│       ▼                                                          │
│  ┌──────────────────┐    ┌──────────────────┐                 │
│  │ event == "messages" │    │ event == "custom" │            │
│  └─────────┬──────────┘    └─────────┬──────────┘                 │
│            │                           │                           │
│            ▼                           ▼                           │
│  ┌─────────────────────┐    ┌─────────────────────┐            │
│  │ 处理 msg_list:      │    │ 处理自定义事件:    │            │
│  │ - AIMessageChunk   │    │ - generated_files  │            │
│  │ - tool             │    │ - 其他类型...      │            │
│  └─────────────────────┘    └─────────────────────┘            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 五、事件详解

### 5.1 messages 事件

见后文"详细消息类型说明"

### 5.2 custom 事件

见后文"详细消息类型说明"

### 5.3 metadata 事件

见后文"详细消息类型说明"

---

## 六、详细消息类型说明

### 6.1 messages 事件

#### 数据结构

```python
(event_name, data)
# event_name = "messages"
# data = [msg_list, metadata]
```

- `msg_list`: 消息列表（数组）
- `metadata`: 元数据，包含 langgraph_node, step 等信息

#### 消息类型

| 类型 | 说明 | 出现场景 |
|------|------|----------|
| `AIMessageChunk` | AI 消息块 | LLM 流式输出文本或工具调用 |
| `tool` | 工具执行结果 | 工具执行完成后返回 |
| `system` | 系统消息 | 系统提示词 |
| `human` | 用户消息 | 用户输入 |
| `text` | 文本块 | 文本内容片段 |

---

### 6.2 AIMessageChunk - AI 消息块

这是最常见的消息类型，用于 LLM 流式输出的各个阶段。

### 数据结构

```python
{
    "type": "AIMessageChunk",
    "id": "lc_run--019ca315-5679-7c02-a20d-c6b69e10d8a5",  # 消息 ID
    "content": "这是 LLM 输出的文本内容",  # 文本内容
    "tool_calls": [...],          # 工具调用列表
    "tool_call_chunks": [...],   # 工具调用参数块
    "response_metadata": {
        "model_provider": "openai",
        "finish_reason": "tool_calls"  # 结束原因：stop / tool_calls
    }
}
```

### 场景分类

#### 2.1 普通文本输出

LLM 输出普通文本时：

```python
{
    "type": "AIMessageChunk",
    "content": "我需要读取论文内容",
    "tool_calls": [],
    "tool_call_chunks": []
}
```

**输出**: 直接打印 `content` 内容

#### 2.2 工具调用开始

当 LLM 决定调用工具时：

```python
{
    "type": "AIMessageChunk",
    "tool_calls": [
        {
            "name": "write_file",           # 工具名称
            "args": {},                      # 参数（初始为空 dict）
            "id": "call_285299eb6b9045e8b878ebc7",  # 工具调用 ID
            "type": "tool_call"
        }
    ],
    "tool_call_chunks": [
        {
            "name": "write_file",
            "args": "",
            "id": "call_xxx",
            "index": 0,
            "type": "tool_call_chunk"
        }
    ]
}
```

**输出**:
```
🔧 工具: write_file
   ID: call_xxx
📝 参数:
```

#### 2.3 参数流式输出

参数通过 `tool_call_chunks` 分片传输：

```python
# 第一帧
{
    "tool_call_chunks": [
        {
            "name": "write_file",
            "args": '{"file_path": "/deepthink',
            "id": "call_xxx",
            "index": 0
        }
    ]
}

# 第二帧
{
    "tool_call_chunks": [
        {
            "name": "write_file",
            "args': '/final_report.md", "content": "# 毕业',
            "id": "call_xxx",
            "index": 0
        }
    ]
}
```

**输出**: 实时追加显示参数内容

#### 2.4 消息结束

`chunk_position: "last"` 表示这是最后一个块：

```python
{
    "type": "AIMessageChunk",
    "content": "",
    "tool_calls": [],
    "response_metadata": {
        "finish_reason": "tool_calls"  # 或 "stop"
    },
    "chunk_position": "last"
}
```

---

## 3. tool - 工具执行结果

工具执行完成后返回的消息类型。

### 数据结构

```python
{
    "type": "tool",
    "name": "write_file",                    # 工具名称
    "content": "Updated file /deepthink/final_report.md",  # 返回内容
    "tool_call_id": "call_xxx",            # 关联的调用 ID
    "status": "success"                      # 执行状态：success / error
}
```

### 常见工具的返回格式

#### write_file 工具

```python
{
    "type": "tool",
    "name": "write_file",
    "content": "Updated file /deepthink/final_report.md",
    "tool_call_id": "call_xxx",
    "status": "success"
}
```

#### read_file 工具

```python
{
    "type": "tool",
    "name": "read_file",
    "content": "# 论文标题\n\n这是论文内容...",
    "tool_call_id": "call_xxx",
    "status": "success"
}
```

#### execute 工具（命令执行）

```python
{
    "type": "tool",
    "name": "execute",
    "content": "命令输出内容...",
    "tool_call_id": "call_xxx",
    "status": "success"
}
```

#### write_todos 工具

```python
{
    "type": "tool",
    "name": "write_todos",
    "content": "Updated todo list to [{'id': '1', 'content': '任务1', 'status': 'in_progress'}, ...]",
    "tool_call_id": "call_xxx",
    "status": "success"
}
```

**特殊处理**: 需要解析为任务清单格式

---

## 4. custom 事件

自定义事件，用于传输额外信息。

### 数据结构

```python
{
    "type": "custom",
    "data": {
        "type": "generated_files",
        "content": ["deepthink/final_report.md", "output/summary.json"]
    }
}
```

### 类型分类

#### generated_files - 生成的文件列表

```python
{
    "type": "custom",
    "data": {
        "type": "generated_files",
        "content": [
            "deepthink/final_report.md",
            "deepthink/test_report.md"
        ]
    }
}
```

**输出**:
```
📁 生成的文件:
   - deepthink/final_report.md
   - deepthink/test_report.md
```

---

## 5. metadata 事件

包含运行的元数据信息。

### 数据结构

```python
{
    "event": "metadata",
    "data": {
        "run_id": "019ca301-1c09-79c0-a75f-70cf717400ab",
        "attempt": 1
    }
}
```

---

## 数据流图

### 完整消息流程

```
┌─────────────────────────────────────────────────────────────────┐
│                     LangGraph Stream Events                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  messages 事件链:                                                │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ AIMessage    │    │ AIMessage   │    │ AIMessage    │       │
│  │ (文本块)     │ -> │ (工具调用)  │ -> │ (参数流式)   │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│         │                   │                   │                  │
│         v                   v                   v                  │
│  "我正在分析..."      🔧 工具: xxx       参数片段...            │
│                       ID: call_xxx                              │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐                         │
│  │ tool         │    │ AIMessage     │                         │
│  │ (工具结果)   │    │ (结束标记)    │                         │
│  └──────────────┘    └──────────────┘                         │
│         │                                                       │
│         v                                                       │
│  ✅ 结果: xxx                                                   │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│  custom 事件:                                                   │
│  📁 生成的文件:                                                 │
│     - deepthink/final_report.md                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 工具调用时序图

```
LLM          LangGraph            客户端
 │                │                    │
 │ ──(AIMessageChunk)────>            │
 │    tool_calls: [{                  │
 │      name: "write_file",           │
 │      id: "call_xxx"               │
 │    }]                              │
 │                │                    │  🔧 工具: write_file
 │                │                    │  ID: call_xxx
 │ ──(AIMessageChunk)────>            │
 │    tool_call_chunks:                │
 │    [{args: '{"file_'              │
 │                │                    │  📝 参数: {"file_
 │ ──(AIMessageChunk)────>            │
 │    tool_call_chunks:                │
 │    [{args: 'path": "/...'         │
 │                │                    │  📝 参数: path": "/...
 │ ──────────────>│                    │
 │    tool: {content: "..."}          │
 │                │                    │  ✅ 结果: ...
 │                │                    │
```

---

## 代码处理示例

### 完整处理流程

```python
async def output_stream_result(chunks, chunk_file=None):
    global tool_calls_registry
    tool_calls_registry = {}

    async for chunk in chunks:
        event_name = chunk.event
        data = chunk.data

        # 1. 处理 custom 事件
        if event_name == "custom":
            handle_custom_event(data)
            continue

        # 2. 处理 messages 事件
        if event_name == "messages":
            msg_list = data[0]

            for msg in msg_list:
                msg_type = msg.get('type')

                # 2.1 AI 消息块
                if msg_type == "AIMessageChunk":
                    handle_ai_message_chunk(msg)

                # 2.2 工具结果
                elif msg_type == "tool":
                    handle_tool_result(msg)
```

### 处理 AI 消息块

```python
# 全局变量：标记上一个是否是工具调用结果
last_tool_call_ended = False

def handle_ai_message_chunk(msg):
    global last_tool_call_ended
    content = msg.get('content', '')
    tool_calls = msg.get('tool_calls', [])
    tool_call_chunks = msg.get('tool_call_chunks', [])

    # 输出文本内容
    if content:
        # 如果上一个是工具调用结果，先换行
        if last_tool_call_ended:
            print("\n")  # 换行
            last_tool_call_ended = False  # 重置标记
        print(content, end='', flush=True)

    # 处理工具调用开始
    for tc in tool_calls:
        tool_name = tc.get('name', '')
        tool_id = tc.get('id', '')

        if tool_name and tool_id:
            tool_calls_registry[tool_id] = {'name': tool_name, 'args': ''}
            print(f"\n🔧 工具: {tool_name}")
            print(f"   ID: {tool_id}")
            print(f"📝 参数: ", end='')

    # 处理参数流式
    for tcc in tool_call_chunks:
        args_chunk = tcc.get('args', '')
        print(f"{args_chunk}", end='', flush=True)
```

### 处理工具结果

```python
def handle_tool_result(msg):
    global last_tool_call_ended
    tool_name = msg.get('name')
    tool_content = msg.get('content', '')
    tool_status = msg.get('status')

    print(f"\n✅ 结果: {tool_content}", end='')
    last_tool_call_ended = True  # 标记工具调用已结束

    # 特殊处理：待办列表
    if tool_name == "write_todos" and tool_status == "success":
        todos = parse_todos(tool_content)
        print(f"\n📋 任务清单:")
        for todo in todos:
            status = todo.get('status')
            icon = "✅" if status == "completed" else "⏳"
            print(f"  {icon} {todo.get('content')}")
```

### 处理 custom 事件

```python
def handle_custom_event(data):
    event_type = data.get('type')

    if event_type == "generated_files":
        files = data.get('content', [])
        print(f"\n📁 生成的文件:")
        for f in files:
            print(f"   - {f}")
```

---

## 工具调用与结果匹配

### 匹配机制

通过 `tool_call_id` 关联工具调用和结果：

```
AIMessageChunk (tool_calls):
  tool_call_id: "call_xxx"  ──┐
                               │
                               │  匹配
                               │
tool (ToolMessage):            │
  tool_call_id: "call_xxx"  ──┘
```

### 代码实现

```python
# 1. 调用开始时保存信息
tool_calls_registry[tool_call_id] = {
    'name': tool_name,
    'args': accumulated_args
}

# 2. 结果返回时查找
result_tool_call_id = msg.get('tool_call_id')
tool_info = tool_calls_registry.get(result_tool_call_id)
```

---

## 常见问题

### Q1: 为什么 tool_call 的 name 和 id 有时为空？

在流式输出的中间帧，LLM 还没有完全确定工具名称和 ID，所以可能为空。这是正常的流式行为。

**解决方案**: 只在 `name` 和 `id` 都不为空时才输出调用开始信息。

### Q2: 参数是如何分片的？

参数通过 `tool_call_chunks` 数组传输，每个 chunk 包含参数的一部分。需要累加所有 chunk 的 `args` 才能得到完整参数。

### Q3: 如何判断消息结束？

检查 `chunk_position` 字段：
- `None`: 中间帧
- `"last"`: 最后一帧

或检查 `response_metadata.finish_reason`:
- `"stop"`: 正常结束
- `"tool_calls"`: 需要调用工具

---

## 完整字段参考

### AIMessageChunk

```python
{
    "type": "AIMessageChunk",
    "id": "lc_run--xxx",
    "content": "文本内容",
    "additional_kwargs": {},
    "response_metadata": {
        "model_provider": "openai",
        "finish_reason": "tool_calls"
    },
    "tool_calls": [...],
    "tool_call_chunks": [...],
    "usage_metadata": {...},
    "chunk_position": "last"  # 或 None
}
```

### tool

```python
{
    "type": "tool",
    "name": "write_file",
    "content": "操作结果",
    "tool_call_id": "call_xxx",
    "status": "success",
    "artifact": None
}
```

### metadata

```python
{
    "created_by": "system",
    "assistant_id": "xxx",
    "run_id": "xxx",
    "thread_id": "xxx",
    "graph_id": "research",
    "langgraph_step": 95,
    "langgraph_node": "model",
    "langgraph_triggers": ["branch:to:model"]
}
```
