# 运行时动态工具（Dynamic Schema Tools）教程

本文档介绍如何在 **每次 run 请求时**，通过 `config.configurable` 动态传入工具 schema，让模型生成对应的 tool call 参数，并由后端返回占位结果。

适用场景：

- 前端希望临时为某次对话追加工具定义
- 后端不实际执行工具，只需要拿到模型生成的结构化参数
- 客户端浏览器、桌面端或其他外部 client 自己消费这些参数并执行真实动作

---

## 1. 功能概览

当前实现支持：

1. 在 `config.configurable.dynamic_tools` 中传入工具 schema
2. 在当前 run 的 **LLM tools 请求参数** 中动态追加这些工具
3. 模型发起 tool call 后，由后端 **stub tool** 兜底返回结果
4. 默认返回 `echo` 结果，即原样回显调用参数

这意味着：

- **模型侧** 能看到动态工具定义
- **执行侧** 不会因为 LangChain 固定工具注册表缺少该工具而报错
- **客户端侧** 可以稳定拿到工具名和参数

---

## 2. 代码位置

### 服务端接入点

- 中间件实现：`src/middleware/dynamic_schema_tools.py`
- 主代理接入：`src/graph.py:111`

### 测试脚本

- 端到端脚本：`tests/clients/test_dynamic_schema_tools_sdk.py`

---

## 3. 工作原理

动态工具分成两段处理：

### 3.1 模型调用前注入 tools

在 `DynamicSchemaToolsMiddleware.wrap_model_call / awrap_model_call` 中：

- 从 `config.configurable.dynamic_tools` 读取动态工具定义
- 将 JSON Schema 转换为 `args_schema`
- 构造 `StructuredTool`
- 通过 `request.override(tools=...)` 追加到本次模型请求

这样模型就能在这次 run 中“看到”这些动态工具。

### 3.2 工具执行时拦截

仅仅把 schema 注入给模型还不够。

因为 LangChain 在工具执行阶段仍然优先依赖固定注册的工具列表。若模型调用了一个运行时动态追加的工具名，而执行阶段没有对应真实工具，通常会报：

```text
<tool_name> is not a valid tool
```

为了解决这个问题，本项目在 `DynamicSchemaToolsMiddleware.wrap_tool_call / awrap_tool_call` 中增加了拦截逻辑：

- 如果当前 tool call 的名字来自 `config.configurable.dynamic_tools`
- 则直接返回一个 `ToolMessage(status="success")`
- 不再把该调用交给 LangChain 默认工具执行器

这样即使该工具没有真实 Python 实现，整条 tool call 链路也能闭环。

---

## 4. 请求格式

客户端通过 `Config` 传入动态工具：

```python
from langgraph_sdk.schema import Config

config = Config(
    configurable={
        "dynamic_tools": [
            {
                "name": "browser_click",
                "description": "点击页面元素。当用户明确要求点击页面元素时调用。",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "selector": {
                            "type": "string",
                            "description": "要点击的 CSS selector"
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "等待超时时间，单位毫秒"
                        }
                    },
                    "required": ["selector", "timeout"]
                }
            }
        ]
    }
)
```

字段说明：

| 字段 | 是否必填 | 说明 |
|------|----------|------|
| `name` | 是 | 动态工具名称 |
| `description` | 否 | 工具描述，供模型理解用途 |
| `input_schema` | 否 | JSON Schema，推荐使用 `type=object` |
| `stub_response_mode` | 否 | 占位返回模式，默认 `echo` |
| `stub_response_template` | 否 | 当 `stub_response_mode=template` 时使用 |

---

## 5. 返回模式

### 5.1 默认模式：`echo`

如果不传 `stub_response_mode`，默认返回：

```json
{
  "ok": true,
  "tool": "browser_click",
  "arguments": {
    "selector": "#submit",
    "timeout": 1000
  }
}
```

这是最适合前端消费参数的模式。

### 5.2 `ack`

```json
{
  "name": "browser_click",
  "description": "点击页面元素",
  "input_schema": {"type": "object", "properties": {}},
  "stub_response_mode": "ack"
}
```

返回：

```json
{
  "ok": true,
  "tool": "browser_click",
  "message": "dynamic tool acknowledged"
}
```

### 5.3 `template`

```json
{
  "name": "browser_click",
  "description": "点击页面元素",
  "input_schema": {"type": "object", "properties": {}},
  "stub_response_mode": "template",
  "stub_response_template": "browser click accepted"
}
```

返回：

```json
{
  "ok": true,
  "tool": "browser_click",
  "message": "browser click accepted",
  "arguments": {...}
}
```

---

## 6. 客户端调用示例

使用 `StreamingClient`：

```python
import uuid
from langgraph_sdk.schema import Config
from src.clients import StreamingClient

client = StreamingClient(url="http://localhost:2024", assistant_id="research")
thread_id = str(uuid.uuid4())

config = Config(
    configurable={
        "dynamic_tools": [
            {
                "name": "browser_click",
                "description": "点击页面元素",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string"},
                        "timeout": {"type": "integer"}
                    },
                    "required": ["selector", "timeout"]
                }
            }
        ]
    }
)

async for chunk in client.chat_stream(
    message=(
        "你必须调用一次且仅一次工具 browser_click，"
        "参数 selector 设置为 '#submit'，timeout 设置为 1000。"
        "调用完成后只回复 OK。"
    ),
    thread_id=thread_id,
    config=config,
    multitask_strategy="reject",
    stream_subgraphs=True,
    on_disconnect="cancel",
    on_completion="delete",
    durability="async",
):
    print(chunk)
```

---

## 7. 前端执行后回传结果示例

动态工具最常见的使用方式是：

1. 服务端把动态工具 schema 暴露给模型
2. 模型生成 tool call 参数
3. 前端拿到参数后执行真实动作
4. 前端把执行结果再发回服务端，进入下一轮推理

示例流程：

### 第一步：模型生成 tool call

模型调用：

```json
{
  "name": "browser_click",
  "args": {
    "selector": "#submit",
    "timeout": 1000
  }
}
```

后端 stub 返回：

```json
{
  "ok": true,
  "tool": "browser_click",
  "arguments": {
    "selector": "#submit",
    "timeout": 1000
  }
}
```

### 第二步：前端执行真实动作

例如浏览器端拿到参数后执行：

```javascript
const args = { selector: "#submit", timeout: 1000 };
const element = document.querySelector(args.selector);
if (!element) {
  throw new Error(`元素不存在: ${args.selector}`);
}
element.click();
```

### 第三步：把执行结果作为下一轮消息回传

前端可以将真实执行结果重新发回服务端：

```python
async for chunk in client.chat_stream(
    message=(
        "上一轮工具 browser_click 已由客户端真实执行。"
        "执行结果如下：selector=#submit，status=success，"
        "页面提示：提交成功。"
        "请基于这个结果继续下一步分析。"
    ),
    thread_id=thread_id,
    config=Config(configurable={}),
):
    print(chunk)
```

如果你希望更结构化，也可以把执行结果包装成明确的 JSON 文本再发回，例如：

```json
{
  "tool": "browser_click",
  "executed_by": "frontend",
  "status": "success",
  "selector": "#submit",
  "message": "提交成功"
}
```

推荐实践：

- **模型负责决策与参数生成**
- **前端负责真实执行**
- **服务端负责上下文衔接**

---

## 8. 端到端测试

运行测试脚本：

```bash
uv run python tests/clients/test_dynamic_schema_tools_sdk.py
```

期望输出类似：

```text
✅ 动态 schema 工具测试完成
工具调用次数: 1
工具参数: {'selector': '#submit', 'timeout': 1000}
工具返回: {'ok': True, 'tool': 'browser_click', 'arguments': {'selector': '#submit', 'timeout': 1000}}
AI 输出: OK
```

---

## 9. 支持的 schema 类型

当前 JSON Schema 到 Pydantic 的转换支持这些基础类型：

- `string`
- `integer`
- `number`
- `boolean`
- `array`
- `object`

说明：

1. 推荐使用 `type: object` 作为顶层 schema
2. 支持嵌套 object
3. 若 `input_schema` 缺失或不是 object，会回退为宽松 `payload` 模式
4. 字段名若包含特殊字符，会自动转成安全 Python 字段名，并保留 alias

---

## 10. 注意事项

### 9.1 生效范围是 run 级

动态工具只对当前请求生效，不会持久化到 thread。

### 9.2 不是真实业务执行

当前实现的目标是：

- 让模型生成结构化参数
- 让后端安全地返回 stub result

它**不负责真实浏览器点击、JS 执行或外部系统调用**。

真实动作需要由客户端自己完成。

### 9.3 如果要继续多轮推理

如果你希望模型根据“客户端执行后的真实结果”继续推理，需要客户端把执行结果再作为下一轮消息发回服务端。

例如：

1. 模型调用 `browser_click`
2. 客户端拿到参数并执行真实点击
3. 客户端把执行结果作为下一轮用户消息或工具结果回传

### 9.4 服务端重启

如果你修改了 `src/middleware/dynamic_schema_tools.py` 或 `src/graph.py`，需要确保 LangGraph 服务重新加载新代码。否则你可能看到：

```text
<tool_name> is not a valid tool
```

---

## 11. 常见问题

### Q1：为什么只注入 `request.tools` 还不够？

因为模型看到工具 schema 后，执行阶段仍然可能走 LangChain 固定工具表校验。只改模型请求不改执行拦截，动态工具仍然可能在执行时失败。

### Q2：为什么后端不直接执行浏览器操作？

这是本功能的设计边界。本功能只负责“动态 schema + 参数闭环”，真实执行留给客户端。

### Q3：可以和默认工具一起使用吗？

可以。当前实现是 **追加模式**：

```text
默认工具 + dynamic_tools
```

### Q4：如果动态工具名和已有工具重名怎么办？

当前实现会跳过重名动态工具，避免覆盖现有固定工具。

---

## 12. 推荐实践

如果你的目标是前端执行真实动作，推荐这样设计：

1. 前端通过 `dynamic_tools` 注入 schema
2. 模型生成结构化参数
3. 后端返回 `echo arguments`
4. 前端监听 tool call / tool result
5. 前端执行真实动作（浏览器、桌面端、移动端等）
6. 如需继续推理，再把执行结果发回服务端

这种模式最适合：

- 浏览器自动化
- 客户端 JS 调用
- Electron / 原生端桥接
- 第三方业务 API 由前端代执行

---

## 13. 相关文件

- `src/middleware/dynamic_schema_tools.py`
- `src/graph.py`
- `tests/clients/test_dynamic_schema_tools_sdk.py`
- `docs/dynamic-model.md`
- `docs/tools.md`
