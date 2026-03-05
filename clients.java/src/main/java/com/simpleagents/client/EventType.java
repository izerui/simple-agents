package com.simpleagents.client;

/**
 * 流式事件类型枚举.
 */
public enum EventType {
    /**
     * AI 消息块（流式输出）
     */
    AI_MESSAGE_CHUNK("ai_message_chunk"),

    /**
     * 工具消息
     */
    TOOL_MESSAGE("tool_message"),

    /**
     * 工具调用完整结果（参数 + 结果）
     */
    TOOL_CALL_COMPLETE("tool_call_complete"),

    /**
     * 自定义事件
     */
    CUSTOM("custom"),

    /**
     * 错误
     */
    ERROR("error");

    private final String value;

    EventType(String value) {
        this.value = value;
    }

    public String getValue() {
        return value;
    }

    /**
     * 从字符串值获取枚举.
     */
    public static EventType fromValue(String value) {
        for (EventType type : EventType.values()) {
            if (type.value.equals(value)) {
                return type;
            }
        }
        return null;
    }
}
