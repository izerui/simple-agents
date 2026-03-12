# 从 Agent 消息中提取工具调用

本文档说明如何在 Agent 执行完成后，从消息中提取工具调用的参数。

## 模式说明

当 Agent 调用某个工具时，工具调用的信息会存储在消息的 `tool_calls` 字段中。我们可以通过遍历消息来提取特定工具的调用参数。

## 代码示例

```python
from typing import Any, TypedDict
from langchain.agents.middleware import AgentMiddleware, AgentState


class CustomState(TypedDict):
    """扩展的 Agent State"""
    custom_field: list[str]


class CustomMiddleware(AgentMiddleware):
    """提取 Agent 工具调用并发送 custom 事件"""

    # 定义 state_schema
    state_schema = CustomState

    async def aafter_agent(self, state: AgentState, runtime: Any) -> dict | None:
        """在 Agent 执行完成后提取工具调用"""
        messages = state.get("messages", [])
        if not messages:
            return None

        # 遍历消息查找工具调用
        result = []
        for msg in messages:
            # 检查是否有 tool_calls
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    # 检查是否是目标工具
                    if tool_call.get('name') == '目标工具名称':
                        # 提取参数
                        args = tool_call.get('args', {})
                        # 提取需要的字段
                        result.append(args.get('参数名'))

        if result:
            # 发送 custom 事件给前端
            runtime.stream_writer({
                "type": "custom_type",
                "content": result
            })
            # 持久化到 state
            return {"custom_field": result}

        return None
```

## 关键点

1. **tool_calls 结构**：
   - `tool_call['name']`: 工具名称
   - `tool_call['args']`: 工具参数（字典）

2. **消息类型**：
   - 工具调用信息存储在 `AIMessage` 的 `tool_calls` 字段中
   - 需要遍历所有消息来查找

3. **state_schema**：
   - 定义 `TypedDict` 来扩展 Agent State
   - 设置 `state_schema` 让 create_agent 自动合并到 state

4. **stream_writer**：
   - 通过 `runtime.stream_writer()` 发送自定义事件
   - 前端可以通过监听 `custom` 事件接收

## 注册 Middleware

在 `graph.py` 中注册：

```python
from src.middleware.suggested_questions import SuggestedQuestionsMiddleware

agent = create_deep_agent(
    # ...
    middlewares=[
        # ...
        SuggestedQuestionsMiddleware(),
    ],
)
```
