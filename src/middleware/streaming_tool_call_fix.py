"""修复流式输出工具调用参数缺失问题的中间件。

某些模型（如 Qwen3-max 等 DashScope 兼容 API 调用的模型都存在流式工具调用的问题）在流式输出工具调用时，
会将 name 和 args 分成多个 chunks 返回，导致最终 tool_calls 包含两个分离的条目：
  - 第一个：{name: 'ls', args: {}}  ← 参数丢失
  - 第二个：{name: '', args: {path: '/files'}}  ← 名称丢失

此外，DashScope API 在流式模式下返回的 tool_calls.args 可能是 JSON 字符串格式，
但 LangChain 内部使用字典格式存储 args，导致多轮对话时 Pydantic 校验失败。

这个中间件通过：
1. 在模型返回后，合并分离的 tool_calls 条目
2. 智能保持原始格式：如果原始 args 是 JSON 字符串，合并后仍为 JSON 字符串
3. 如果原始 args 是字典，合并后仍为字典

鱼和熊掌兼得的方案：
- 修复 DashScope 的分离问题
- 满足 code model 对 JSON 字符串格式的严格要求
- 不影响其他模型（GLM、DeepSeek 等）

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

import json
import logging
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime
from langgraph.types import Overwrite

logger = logging.getLogger(__name__)


def _detect_args_format(args: Any) -> str:
    """检测 args 的格式类型。

    Args:
        args: 任意类型的参数

    Returns:
        'json_string' - 是有效的 JSON 字符串
        'dict' - 是字典
        'other' - 其他类型
    """
    if args is None:
        return 'other'
    
    if isinstance(args, str):
        try:
            json.loads(args)
            return 'json_string'
        except json.JSONDecodeError:
            return 'other'
    
    if isinstance(args, dict):
        return 'dict'
    
    return 'other'


def _parse_args_to_dict(args: Any) -> dict:
    """将 args 安全地解析为字典格式。

    Args:
        args: 可以是 None、字典、JSON 字符串或其他类型

    Returns:
        字典格式的 args，如果无法转换则返回空字典
    """
    if args is None:
        return {}
    
    if isinstance(args, dict):
        return args.copy()  # 返回副本避免修改原始数据
    
    if isinstance(args, str):
        try:
            parsed = json.loads(args)
            if isinstance(parsed, dict):
                return parsed
            else:
                # 解析成功但不是字典，返回空字典
                return {}
        except json.JSONDecodeError:
            # 不是有效的 JSON，返回空字典
            return {}
    
    # 其他类型，返回空字典
    return {}


def _format_args_from_dict(args_dict: dict, target_format: str) -> Any:
    """将字典格式化为目标格式。

    Args:
        args_dict: 字典格式的参数
        target_format: 目标格式 ('json_string' 或 'dict')

    Returns:
        如果目标格式是 'json_string'，返回 JSON 字符串
        如果目标格式是 'dict'，返回字典
    """
    if target_format == 'json_string':
        try:
            return json.dumps(args_dict)
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to serialize args to JSON: {e}")
            return '{}'
    else:
        # 保持为字典
        return args_dict


def _needs_merge(tool_calls: list[dict]) -> bool:
    """检测 tool_calls 是否需要合并。

    如果存在只有 name 或只有 args 的条目，说明需要合并。

    Args:
        tool_calls: 工具调用列表

    Returns:
        如果需要合并则返回 True
    """
    if not tool_calls:
        return False

    for tc in tool_calls:
        has_name = bool(tc.get('name'))
        has_args = bool(tc.get('args'))
        # 如果只有其中一个，说明需要合并
        if has_name != has_args:
            return True

    return False


def _get_original_args_format(tool_calls: list[dict]) -> str:
    """检测 tool_calls 中 args 的原始格式。

    Args:
        tool_calls: 工具调用列表

    Returns:
        'json_string' - 如果存在 JSON 字符串格式的 args
        'dict' - 否则假设为字典格式
    """
    for tc in tool_calls:
        args = tc.get('args')
        if args is not None:
            format_type = _detect_args_format(args)
            if format_type == 'json_string':
                return 'json_string'
    
    # 如果没有找到 JSON 字符串，默认为字典格式
    return 'dict'


def fix_streaming_tool_calls(tool_calls: list[dict]) -> list[dict]:
    """修复流式输出的工具调用参数分离问题。

    关键特性：
    1. 将分离的 tool_calls 条目合并成一个完整的工具调用
    2. 智能保持原始格式：如果原始 args 是 JSON 字符串，合并后仍为 JSON 字符串
    3. 如果原始 args 是字典，合并后仍为字典

    Args:
        tool_calls: 原始工具调用列表

    Returns:
        修复后的工具调用列表
    """
    if not tool_calls:
        return tool_calls

    # 检测是否需要修复：存在只有 name 或只有 args 的条目
    if not _needs_merge(tool_calls):
        return tool_calls

    # 检测原始 args 的格式
    original_format = _get_original_args_format(tool_calls)
    logger.debug(f"Detected original args format: {original_format}")

    # 合并策略：按 id 分组，如果没有 id 则按顺序合并
    merged = {}
    current_id = None

    for tc in tool_calls:
        tc_id = tc.get('id') or current_id
        name = tc.get('name', '')
        
        # 将 args 解析为字典以便合并
        args = _parse_args_to_dict(tc.get('args'))

        if tc_id not in merged:
            merged[tc_id] = {
                'name': name,
                'args': args,
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

    # 将结果转换为列表并格式化 args
    result = []
    for tc in merged.values():
        # 根据原始格式转换 args
        tc['args'] = _format_args_from_dict(tc['args'], original_format)
        result.append(tc)

    return result


class StreamingToolCallFixMiddleware(AgentMiddleware):
    """修复流式输出工具调用参数缺失问题的中间件。

    这个中间件在模型返回后修复 tool_calls，
    在 agent 执行工具调用之前运行。

    鱼和熊掌兼得的方案：
    1. 检测原始 args 的格式（JSON 字符串或字典）
    2. 合并分离的 tool_calls 条目
    3. 保持原始格式：如果原始是 JSON 字符串，合并后仍为 JSON 字符串

    优点：
    - 修复 DashScope 流式输出的分离问题
    - 满足 code model 对 JSON 字符串格式的严格要求
    - 不影响其他模型（GLM、DeepSeek 等）
    - 最小化修改：只在需要合并时才处理

    对所有模型生效，但只会在检测到需要修复时才处理。
    """

    def after_model(self, state: AgentState, runtime: Runtime[Any]) -> dict[  # noqa: ARG002
            str, Any] | None:
        """在模型调用后修复 AIMessage 中的工具调用。

        使用 Overwrite 来替换整个 messages 列表，
        而不是追加新消息，以避免破坏消息历史的连续性。

        Args:
            state: 代理状态
            runtime: 运行时上下文

        Returns:
            状态更新字典，如果没有需要修复的则返回 None
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

        # 检测是否需要修复
        if not _needs_merge(last_msg.tool_calls):
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