"""事件类型定义."""

from enum import Enum


class EventType(str, Enum):
    """流式事件类型."""

    # 消息事件
    AI_MESSAGE_CHUNK = "ai_message_chunk"  # AI 消息块（流式输出）
    TOOL_MESSAGE = "tool_message"  # 工具消息
    TOOL_CALL_COMPLETE = "tool_call_complete"  # 工具调用完整结果（参数 + 结果）

    # 自定义事件
    CUSTOM = "custom"  # 自定义事件

    # 错误
    ERROR = "error"  # 错误
