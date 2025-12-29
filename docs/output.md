事件类型 | 是否展示给用户 | 说明 |
|---------|--------------|------|
| `on_chat_model_stream` | ✅ 是 | 实时输出内容 |
| `on_chat_model_end` | ⚠️ 可能 | 用于汇总统计（如 token 使用量） |
| `on_tool_start` | ✅ 是 | 告知用户在做什么 |
| `on_tool_end` | ⚠️ 可能 | 显示工具结果（如果对用户有用） |
| `on_chain_end` | ⚠️ 可能 | 显示执行进度 |
| `on_agent_action` | ✅ 是 | 显示 Agent 思考过程 |
| `on_chain_start` | ❌ 否 | 内部实现细节 |
| `on_prompt_start/end` | ❌ 否 | 用户不关心 |
| `on_llm_new_token` | ❌ 否 | 使用 on_chat_model_stream 替代



过程：
```
async for event in agent.astream_events(inputs, version="v1", config=config):
    kind = event["event"]
    
    # 1. 显示实时文本（打字机效果）
    if kind == "on_chat_model_stream":
        content = event["data"]["chunk"].content
        if content:
            print(content, end="", flush=True)
    
    # 2. 显示工具调用（增强透明度）
    elif kind == "on_tool_start":
        print(f"\n🔧 正在调用: {event['name']}")
    
    # 3. 显示执行步骤
    elif kind == "on_chain_end":
        print(f"\n✅ [{event['name']}] 完成")
    
    # 4. 错误处理
    elif kind.endswith("_error"):
        print(f"\n❌ 出错: {event['data'].get('error')}")
```