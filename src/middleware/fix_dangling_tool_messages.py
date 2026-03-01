"""修复手动停止工具调用后消息历史不完整问题的中间件。

当用户手动停止 AI 的工具调用后，消息历史中可能会留下孤立的 ToolMessage，
这些 ToolMessage 没有对应的包含 tool_calls 的 AIMessage，导致再次提问时报错：
"messages with role 'tool' must be a response to a preceding message with 'tool_calls'"

这个中间件在 agent 执行前清理这些孤立的 ToolMessage。

使用方法：
    from src.middleware.fix_dangling_tool_messages import FixDanglingToolMessagesMiddleware

    agent = create_deep_agent(
        ...
        middleware=[
            FixDanglingToolMessagesMiddleware(),
            ...
        ],
    )
"""

from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langgraph.runtime import Runtime
from langgraph.types import Overwrite


class FixDanglingToolMessagesMiddleware(AgentMiddleware):
    """修复手动停止工具调用后遗留的孤立 ToolMessage。

    当用户手动中断工具调用时，可能会在消息历史中留下孤立的 ToolMessage，
    这些消息没有对应的 AIMessage 包含 tool_calls。
    此中间件在 agent 执行前检测并移除这些孤立的消息。
    """

    def before_agent(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:  # noqa: ARG002
        """在 agent 运行前清理孤立的 ToolMessage。

        Args:
            state: 代理状态
            runtime: 运行时上下文

        Returns:
            状态更新字典，如果不需要修复则返回 None
        """
        messages = state.get("messages", [])
        if not messages:
            return None

        # 收集所有有效的 tool_call_id（来自包含 tool_calls 的 AIMessage）
        valid_tool_call_ids: set[str] = set()
        for msg in messages:
            if msg.type == "ai" and hasattr(msg, "tool_calls") and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    valid_tool_call_ids.add(tool_call["id"])

        # 过滤掉孤立的 ToolMessage
        filtered_messages = []
        for msg in messages:
            if msg.type == "tool":
                tool_call_id = getattr(msg, "tool_call_id", None)
                if tool_call_id and tool_call_id not in valid_tool_call_ids:
                    # 跳过孤立的 ToolMessage
                    continue
            filtered_messages.append(msg)

        # 如果有消息被过滤，返回更新后的消息列表
        if len(filtered_messages) != len(messages):
            return {"messages": Overwrite(filtered_messages)}

        return None
