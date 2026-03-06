# LangGraph API System Message 问题与解决方案

## 问题描述

在使用 LangGraph API 时，如果在输入的 `messages` 中传入 `role: "system"` 的消息，某些模型（如 MiniMax/MiniMax-M2.5）会报错：

```
APIError: invalid params, invalid chat setting (2013)
```

## 根本原因

LangGraph 的 `create_agent` 内部处理逻辑导致会发送**两个 SystemMessage** 到 API：

### 源码分析 (langchain/agents/factory.py)

```python
# 第 1295-1306 行：amodel_node
def amodel_node(state, runtime):
    request = ModelRequest(
        model=model,
        system_message=system_message,  # 这是 create_agent 传入的 BASE_AGENT_PROMPT
        messages=state["messages"],     # 这是用户传入的 messages
        ...
    )

# 第 1275-1281 行：_execute_model_async
async def _execute_model_async(request):
    messages = request.messages
    if request.system_message:
        messages = [request.system_message, *messages]  # 问题所在！

    output = await model_.ainvoke(messages)
```

当用户传入 `[{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]` 时：

1. `request.system_message` = BASE_AGENT_PROMPT（create_agent 传入的默认 prompt）
2. `request.messages` = 用户传入的 SystemMessage + HumanMessage
3. 最终发送的消息：`[BASE_AGENT_PROMPT, 用户SystemMessage, HumanMessage]`

**结果：两个 SystemMessage！**

某些模型（如 MiniMax/MiniMax-M2.5）走官方 API 通道，对多个 system message 检查更严格，会报错。

## 解决方案

### 方案一：使用 SystemPromptMiddleware（推荐）

在 `src/middleware/` 下创建 `system_prompt.py`：

```python
"""自定义 system prompt 处理中间件"""
from langchain.agents.middleware.types import AgentMiddleware, ModelRequest
from langchain_core.messages import SystemMessage

class SystemPromptMiddleware(AgentMiddleware):
    """从输入中提取 system message，替换默认 prompt"""

    def wrap_model_call(self, request, handler):
        modified_request = self._extract_system_message(request)
        return handler(modified_request)

    async def awrap_model_call(self, request, handler):
        modified_request = self._extract_system_message(request)
        return await handler(modified_request)

    def _extract_system_message(self, request):
        messages = request.messages
        system_messages = [m for m in messages if isinstance(m, SystemMessage)]
        if not system_messages:
            return request

        user_system_msg = system_messages[0]

        # 合并到已有的 system_message
        if request.system_message:
            combined_content = list(user_system_msg.content_blocks)
            combined_content.extend(request.system_message.content_blocks)
            new_system_message = SystemMessage(content_blocks=combined_content)
        else:
            new_system_message = user_system_msg

        # 从 messages 中移除 system message
        filtered_messages = [m for m in messages if not isinstance(m, SystemMessage)]

        return request.override(
            system_message=new_system_message,
            messages=filtered_messages,
        )
```

在 `src/graph.py` 中添加中间件：

```python
from src.middleware.system_prompt import SystemPromptMiddleware

agent = create_deep_agent(
    ...
    middleware=[
        SystemPromptMiddleware(default_system_prompt=MAIN_AGENT_INSTRUCTIONS),
        ...
    ],
)
```

### 方案二：修复 LangGraph 源码

在 `langchain/agents/factory.py` 的 `_execute_model_async` 中添加过滤逻辑：

```python
async def _execute_model_async(request):
    messages = request.messages
    if request.system_message:
        # 过滤掉 messages 中的 SystemMessage，避免重复
        filtered_messages = [
            m for m in messages
            if not isinstance(m, SystemMessage)
        ]
        messages = [request.system_message, *filtered_messages]

    output = await model_.ainvoke(messages)
```

## 使用方式

### 传递自定义 system message

```bash
curl -X POST http://localhost:2024/runs/stream \
  -H "Content-Type: application/json" \
  -d '{
    "assistant_id": "research",
    "input": {
      "messages": [
        {"role": "system", "content": "你是一个专业的技术顾问"},
        {"role": "user", "content": "你好"}
      ]
    },
    "config": {
      "configurable": {
        "model": "MiniMax/MiniMax-M2.5"
      }
    }
  }'
```

中间件会自动：
1. 提取输入中的 system message
2. 与默认 agent prompt 合并
3. 从输入消息中移除重复的 system message

## 相关文件

- `src/middleware/system_prompt.py` - 自定义中间件
- `src/graph.py` - Agent 定义
- `.venv/lib/python3.12/site-packages/langchain/agents/factory.py` - LangGraph 源码
