package com.simpleagents.client;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 事件处理器抽象基类.
 *
 * 使用方式:
 * <pre>
 * StreamingEventHandlers handler = new SimpleStreamingEventHandlers();
 * client.chatStream("你好", handler);
 * </pre>
 *
 * 可继承并覆盖以下方法:
 * - onAiMessageChunk(content, isChunkStart)  // AI 文本流式
 * - onToolCallStart(toolId, toolName)  // 工具调用开始
 * - onToolCallArgsChunk(toolId, argsChunk, isChunkStart)  // 参数流式
 * - onToolResultChunk(toolId, content, isChunkStart)  // 结果流式
 * - onToolCallComplete(toolId, toolName, args, content, status)  // 完整结果
 * - onCustom(data)  // 自定义事件
 * - onError(error)  // 错误
 */
public abstract class StreamingEventHandlers {

    private static final Logger logger = LoggerFactory.getLogger(StreamingEventHandlers.class);
    protected final Gson gson = new Gson();

    /**
     * 工具调用注册表: {tool_id: {name, args}}
     */
    private final Map<String, ToolCallInfo> toolCallsRegistry = new ConcurrentHashMap<>();

    /**
     * 标记：工具调用是否刚刚完成（用于 onAiMessageChunk 换行判断）
     */
    protected boolean lastToolCallEnded = false;

    /**
     * 记录参数是否已开始
     */
    private final Map<String, Boolean> toolArgsStarted = new ConcurrentHashMap<>();

    /**
     * 记录结果是否已开始
     */
    private final Map<String, Boolean> toolResultStarted = new ConcurrentHashMap<>();

    /**
     * 接收原始 chunk，解析并分发事件.
     *
     * @param event  事件名称
     * @param data   事件数据
     */
    public void receiveChunk(String event, Object data) {
        try {
            if (event == null) {
                return;
            }

            // 自定义事件
            if ("custom".equals(event) && data instanceof Map) {
                @SuppressWarnings("unchecked")
                Map<String, Object> customData = (Map<String, Object>) data;
                onCustom(customData);
                return;
            }

            // 消息事件
            if ("messages".equals(event)) {
                if (!(data instanceof List) || ((List<?>) data).size() < 2) {
                    return;
                }

                @SuppressWarnings("unchecked")
                List<Object> dataList = (List<Object>) data;
                Object msgListObj = dataList.get(0);

                List<Map<String, Object>> msgList;
                if (msgListObj instanceof List) {
                    @SuppressWarnings("unchecked")
                    List<Object> list = (List<Object>) msgListObj;
                    msgList = new ArrayList<>();
                    for (Object item : list) {
                        if (item instanceof Map) {
                            @SuppressWarnings("unchecked")
                            Map<String, Object> map = (Map<String, Object>) item;
                            msgList.add(map);
                        }
                    }
                } else if (msgListObj instanceof Map) {
                    msgList = Collections.singletonList((Map<String, Object>) msgListObj);
                } else {
                    return;
                }

                for (Map<String, Object> msg : msgList) {
                    if (msg == null) continue;
                    String msgType = (String) msg.get("type");

                    if ("AIMessageChunk".equals(msgType)) {
                        handleAiMessageChunk(msg);
                    } else if ("tool".equals(msgType)) {
                        handleToolMessage(msg);
                    }
                }
            }

        } catch (Exception e) {
            logger.error("Error processing chunk: {}", e.getMessage(), e);
            onError(e);
        }
    }

    /**
     * 处理 AI 消息块.
     */
    private void handleAiMessageChunk(Map<String, Object> msg) {
        Object contentObj = msg.get("content");
        String content = contentObj != null ? contentObj.toString() : "";

        if (content != null && !content.isEmpty()) {
            // 工具调用完成后新一轮 AI 输出开始，需要换行
            boolean isChunkStart = lastToolCallEnded;
            if (isChunkStart) {
                lastToolCallEnded = false;
            }
            onAiMessageChunk(content, isChunkStart);
        }

        // tool_calls - 工具调用开始（args 为空，参数通过 tool_call_chunks 流式传递）
        Object toolCallsObj = msg.get("tool_calls");
        if (toolCallsObj instanceof List) {
            @SuppressWarnings("unchecked")
            List<Object> toolCalls = (List<Object>) toolCallsObj;
            for (int idx = 0; idx < toolCalls.size(); idx++) {
                Object tcObj = toolCalls.get(idx);
                if (tcObj instanceof Map) {
                    @SuppressWarnings("unchecked")
                    Map<String, Object> tc = (Map<String, Object>) tcObj;
                    String toolName = (String) tc.getOrDefault("name", "");
                    String toolId = (String) tc.getOrDefault("id", "");

                    if (toolName != null && !toolName.isEmpty() && toolId != null && !toolId.isEmpty()) {
                        ToolCallInfo info = new ToolCallInfo();
                        info.name = toolName;
                        info.args = "";
                        info.index = idx;
                        toolCallsRegistry.put(toolId, info);
                        onToolCallStart(toolId, toolName);
                    }
                }
            }
        }

        // tool_call_chunks - 参数流式
        Object toolCallChunksObj = msg.get("tool_call_chunks");
        if (toolCallChunksObj instanceof List) {
            @SuppressWarnings("unchecked")
            List<Object> toolCallChunks = (List<Object>) toolCallChunksObj;
            for (Object tccObj : toolCallChunks) {
                if (tccObj instanceof Map) {
                    @SuppressWarnings("unchecked")
                    Map<String, Object> tcc = (Map<String, Object>) tccObj;
                    String tccId = (String) tcc.getOrDefault("id", "");
                    Object tccIndexObj = tcc.get("index");
                    int tccIndex = tccIndexObj != null ? ((Number) tccIndexObj).intValue() : -1;
                    String argsChunk = tcc.get("args") != null ? tcc.get("args").toString() : "";

                    // 累加参数：优先通过 ID，其次通过 index
                    String matchedId = null;
                    boolean isArgsChunkStart = false;

                    if (tccId != null && !tccId.isEmpty() && toolCallsRegistry.containsKey(tccId)) {
                        ToolCallInfo info = toolCallsRegistry.get(tccId);
                        info.args += argsChunk;
                        matchedId = tccId;
                        isArgsChunkStart = !toolArgsStarted.getOrDefault(tccId, false);
                        toolArgsStarted.put(tccId, true);
                    } else if (tccIndex >= 0) {
                        // 通过 index 匹配
                        for (Map.Entry<String, ToolCallInfo> entry : toolCallsRegistry.entrySet()) {
                            if (entry.getValue().index == tccIndex) {
                                entry.getValue().args += argsChunk;
                                matchedId = entry.getKey();
                                isArgsChunkStart = !toolArgsStarted.getOrDefault(entry.getKey(), false);
                                toolArgsStarted.put(entry.getKey(), true);
                                break;
                            }
                        }
                    }

                    // 无论是否找到匹配，都流式输出参数
                    if (argsChunk != null && !argsChunk.isEmpty()) {
                        String outputId = matchedId != null ? matchedId : tccId;
                        onToolCallArgsChunk(outputId != null ? outputId : "", argsChunk, isArgsChunkStart);
                    }
                }
            }
        }
    }

    /**
     * 处理工具消息.
     */
    private void handleToolMessage(Map<String, Object> msg) {
        String toolName = (String) msg.getOrDefault("name", "unknown");
        Object toolContentObj = msg.get("content");
        String toolContent = toolContentObj != null ? toolContentObj.toString() : "";
        String toolCallId = (String) msg.getOrDefault("tool_call_id", "");
        Object toolStatusObj = msg.get("status");
        String toolStatus = toolStatusObj != null ? toolStatusObj.toString() : null;

        // 结果流式
        if (toolContent != null && !toolContent.isEmpty()) {
            boolean isResultChunkStart = !toolResultStarted.getOrDefault(toolCallId, false);
            toolResultStarted.put(toolCallId, true);

            onToolResultChunk(toolCallId, toolContent, isResultChunkStart);
            // 标记工具调用已结束，下一次 AI 输出需要换行
            lastToolCallEnded = true;
        }

        // 完整结果（累积的参数 + 最终结果）
        String args = "";
        if (toolCallId != null && !toolCallId.isEmpty() && toolCallsRegistry.containsKey(toolCallId)) {
            ToolCallInfo toolCallInfo = toolCallsRegistry.remove(toolCallId);
            args = toolCallInfo != null ? toolCallInfo.args : "";
            if (toolCallInfo != null && toolCallInfo.name != null) {
                toolName = toolCallInfo.name;
            }
        }

        onToolCallComplete(toolCallId, toolName, args, toolContent, toolStatus);
    }

    // ========== 抽象方法 - 子类必须实现 ==========

    /**
     * AI 文本流式输出.
     *
     * @param content        AI 输出的文本
     * @param isChunkStart   是否是工具调用完成后新一轮 chunk 开始（需要换行）
     */
    public abstract void onAiMessageChunk(String content, boolean isChunkStart);

    /**
     * 工具调用开始.
     *
     * @param toolId   工具调用 ID
     * @param toolName 工具名称
     */
    public abstract void onToolCallStart(String toolId, String toolName);

    /**
     * 工具参数流式输出.
     *
     * @param toolId        工具调用 ID
     * @param argsChunk     参数字符串片段
     * @param isChunkStart  是否是参数流式开始
     */
    public abstract void onToolCallArgsChunk(String toolId, String argsChunk, boolean isChunkStart);

    /**
     * 工具结果流式输出.
     *
     * @param toolId        工具调用 ID
     * @param content       工具返回的内容
     * @param isChunkStart  是否是结果流式开始
     */
    public abstract void onToolResultChunk(String toolId, String content, boolean isChunkStart);

    /**
     * 工具调用完整结果.
     *
     * @param toolId   工具调用 ID
     * @param toolName 工具名称
     * @param args     完整参数
     * @param content  完整结果
     * @param status   执行状态
     */
    public abstract void onToolCallComplete(String toolId, String toolName, String args, String content, String status);

    /**
     * 自定义事件.
     *
     * @param data 自定义事件数据
     */
    public abstract void onCustom(Map<String, Object> data);

    /**
     * 错误事件.
     *
     * @param error 异常信息
     */
    public abstract void onError(Exception error);

    /**
     * 工具调用信息内部类.
     */
    private static class ToolCallInfo {
        String name;
        String args;
        int index;
    }
}
