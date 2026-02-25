"""修复流式输出工具调用参数缺失问题的中间件。

某些模型（如 Qwen3-max 等 DashScope 兼容 API 调用的模型都存在流式工具调用的问题）在流式输出工具调用时，
会将 name 和 args 分成多个 chunks 返回，导致最终 tool_calls 包含两个分离的条目：
  - 第一个：{name: 'ls', args: {}}  ← 参数丢失
  - 第二个：{name: '', args: {path: '/files'}}  ← 名称丢失

这个中间件通过手动合并这些分离的条目来修复问题。

使用方法：
    from src.middleware.streaming_tool_call_fix import StreamingToolCallFixMiddleware

    agent = create_deep_agent(
        ...
        middleware=[
            StreamingToolCallFixMiddleware(),
            ...
        ],
    )
"""

from __future__ import annotations

import logging
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime
from langgraph.types import Overwrite

logger = logging.getLogger(__name__)


def fix_streaming_tool_calls(tool_calls: list[dict]) -> list[dict]:
    """修复流式输出的工具调用参数分离问题。

    将分离的 tool_calls 条目合并成一个完整的工具调用。
    """
    if not tool_calls:
        return tool_calls

    # 检测是否需要修复：存在只有 name 或只有 args 的条目
    needs_fix = False
    for tc in tool_calls:
        has_name = bool(tc.get('name'))
        has_args = bool(tc.get('args'))
        # 如果只有其中一个，说明需要合并
        if has_name != has_args:
            needs_fix = True
            break

    if not needs_fix:
        return tool_calls

    # 合并策略：按 id 分组，如果没有 id 则按顺序合并
    merged = {}
    current_id = None

    for tc in tool_calls:
        tc_id = tc.get('id') or current_id
        name = tc.get('name', '')
        args = tc.get('args', {})

        if tc_id not in merged:
            merged[tc_id] = {
                'name': name,
                'args': args if args else {},
                'id': tc_id,
                'type': 'tool_call'
            }
        else:
            # 合并到现有条目
            if name:
                merged[tc_id]['name'] = name
            if args:
                merged[tc_id]['args'].update(args)

        if tc_id:
            current_id = tc_id

    result = list(merged.values())
    logger.info(f"Fixed streaming tool calls: {len(tool_calls)} -> {len(result)}")
    return result


class StreamingToolCallFixMiddleware(AgentMiddleware):
    """修复流式输出工具调用参数缺失问题的中间件。

    这个中间件在模型返回后修复 tool_calls，
    在 agent 执行工具调用之前运行。

    对所有模型生效，但只会在检测到需要修复时才处理。
    """

    def after_model(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:  # noqa: ARG002
        """在模型调用后修复 AIMessage 中的工具调用。

        使用 Overwrite 来替换整个 messages 列表，
        而不是追加新消息，以避免破坏消息历史的连续性。
        """
        messages = state.get('messages', [])
        if not messages:
            return None

        # 只检查最后一条消息（最新的 AI 模型响应)
        last_msg = messages[-1] if messages else None
        if not isinstance(last_msg, AIMessage):
            return None
        if not hasattr(last_msg, 'tool_calls') or not last_msg.tool_calls:
            return None

        # 尝试修复
        fixed_tool_calls = fix_streaming_tool_calls(last_msg.tool_calls)
        if fixed_tool_calls == last_msg.tool_calls:
            return None

        # 创建新的消息，替换 tool_calls
        new_msg = AIMessage(
            content=last_msg.content,
            tool_calls=fixed_tool_calls,
            additional_kwargs=last_msg.additional_kwargs,
            response_metadata=last_msg.response_metadata,
            id=last_msg.id,
        )

        # 使用 Overwrite 替换整个消息列表
        # 这样可以保持消息历史的连续性，避免 API 报错
        new_messages = list(messages[:-1]) + [new_msg]

        return {'messages': Overwrite(new_messages)}


# 别名，保持向后兼容
QwenToolCallFixMiddleware = StreamingToolCallFixMiddleware
