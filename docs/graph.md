1. Chain 事件（链操作）
- `on_chain_start` - 链开始执行
- `on_chain_end` - 链执行完成
- `on_chain_error` - 链执行出错
- `on_chain_stream` - 链流式输出

## 2. Tool 事件（工具调用）
- `on_tool_start` - 工具开始执行
- `on_tool_end` - 工具执行完成
- `on_tool_error` - 工具执行出错
- `on_tool_stream` - 工具流式输出

## 3. Chat Model 事件（聊天模型）
- `on_chat_model_start` - 聊天模型开始生成
- `on_chat_model_end` - 聊天模型生成完成
- `on_chat_model_stream` - 聊天模型流式输出（逐个 token）
- `on_chat_model_new_token` - 生成新 token

## 4. LLM 事件（基础语言模型）
- `on_llm_start` - LLM 开始执行
- `on_llm_end` - LLM 执行完成
- `on_llm_stream` - LLM 流式输出
- `on_llm_new_token` - 生成新 token

## 5. Retriever 事件（检索器）
- `on_retriever_start` - 检索器开始检索
- `on_retriever_end` - 检索器检索完成
- `on_retriever_error` - 检索器出错
- `on_retriever_stream` - 检索器流式输出

## 6. Prompt 事件（提示词）
- `on_prompt_start` - 提示词开始处理
- `on_prompt_end` - 提示词处理完成
- `on_prompt_error` - 提示词处理出错

## 7. Agent 特有事件
- `on_agent_action` - Agent 执行某个动作
- `on_agent_finish` - Agent 完成任务

## 8. Graph 特有事件（LangGraph）
- `on_graph_start` - 图开始执行
- `on_graph_end` - 图执行完成
- `on_graph_stream` - 图流式输出