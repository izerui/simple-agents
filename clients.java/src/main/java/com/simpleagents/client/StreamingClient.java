package com.simpleagents.client;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import okhttp3.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.util.*;
import java.util.concurrent.TimeUnit;

/**
 *
 * 使用方式:
 * <pre>
 * StreamingClient client = new StreamingClient("http://localhost:2024", "api_key", "assistant_id");
 * SimpleStreamingEventHandlers handler = new SimpleStreamingEventHandlers();
 *
 * // 简单调用
 * client.chatStream("你好", handler);
 *
 * // 带文件的调用
 * List&lt;FileType&gt; files = List.of(FileType.fromPath("path/to/file.pdf"));
 * client.chatStream("分析这个文件", files, handler);
 *
 * // 带系统提示
 * client.chatStream("你好", null, "你是一个助手", handler);
 * </pre>
 *
 * 支持的文件格式:
 * - 本地文件路径: "path/to/file.pdf" 或 Path 对象
 * - URL: "https://example.com/file.pdf"
 * - 字典格式: {"type": "file", "data": "...", "metadata": {"filename": "..."}}
 */
public class StreamingClient {

    private static final Logger logger = LoggerFactory.getLogger(StreamingClient.class);
    private static final MediaType JSON = MediaType.get("application/json; charset=utf-8");

    private final String url;
    private final String apiKey;
    private final String assistantId;
    private final OkHttpClient httpClient;
    private final Gson gson;

    /**
     * 创建流式客户端.
     *
     * @param url          LangGraph API 地址
     * @param apiKey       API 密钥
     * @param assistantId  助手 ID
     */
    public StreamingClient(String url, String apiKey, String assistantId) {
        this.url = url.endsWith("/") ? url.substring(0, url.length() - 1) : url;
        this.apiKey = apiKey;
        this.assistantId = assistantId;
        this.httpClient = new OkHttpClient.Builder()
                .readTimeout(0, TimeUnit.MILLISECONDS) // 流式响应不使用超时
                .build();
        this.gson = new Gson();
    }

    /**
     * 使用默认参数创建流式客户端.
     *
     * @param url LangGraph API 地址
     */
    public StreamingClient(String url) {
        this(url, "", "research");
    }

    /**
     * 流式聊天（无文件）.
     *
     * @param message  用户消息
     * @param handler 事件处理器
     */
    public void chatStream(String message, StreamingEventHandlers handler) {
        chatStream(message, null, null, null, handler);
    }

    /**
     * 流式聊天（无系统提示）.
     *
     * @param message  用户消息
     * @param files    文件列表
     * @param handler  事件处理器
     */
    public void chatStream(String message, List<FileType> files, StreamingEventHandlers handler) {
        chatStream(message, files, null, null, handler);
    }

    /**
     * 流式聊天（支持文件上传）.
     *
     * @param message      用户消息
     * @param files        文件列表，支持:
     *                     - 本地路径: FileType.fromPath("path/to/file.pdf")
     *                     - URL: FileType.fromUrl("https://example.com/file.pdf")
     *                     - 字典格式: FileType.fromMap(Map.of(...))
     * @param systemPrompt 系统提示
     * @param threadId     线程 ID，null 则使用 "default"
     * @param handler      事件处理器
     */
    public void chatStream(String message, List<FileType> files, String systemPrompt, String threadId, StreamingEventHandlers handler) {
        String resolvedThreadId = threadId != null ? threadId : "default";

        // 构建请求体
        JsonObject requestBody = buildRequestBody(message, files, systemPrompt, resolvedThreadId);

        // 构建 SSE 请求
        String sseUrl = String.format("%s/threads/%s/runs/stream",
                this.url, resolvedThreadId);

        Request request = new Request.Builder()
                .url(buildStreamUrl(resolvedThreadId, requestBody))
                .addHeader("Content-Type", "application/json")
                .addHeader("Accept", "text/event-stream")
                .get()
                .build();

        if (apiKey != null && !apiKey.isEmpty()) {
            request = request.newBuilder()
                    .addHeader("Authorization", "Bearer " + apiKey)
                    .build();
        }

        // 执行流式请求
        try (WebSocket webSocket = httpClient.newBuilder()
                .pingInterval(30, TimeUnit.SECONDS)
                .build()
                .newWebSocket(request, new StreamingWebSocketListener(handler))) {

            // 等待连接完成（简单处理）
            synchronized (this) {
                wait();
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            handler.onError(new RuntimeException("Interrupted", e));
        }
    }

    /**
     * 构建流式请求的 URL（GET 方式）.
     */
    private String buildStreamUrl(String threadId, JsonObject input) {
        StringBuilder urlBuilder = new StringBuilder();
        urlBuilder.append(url);
        urlBuilder.append("/threads/");
        urlBuilder.append(threadId);
        urlBuilder.append("/runs/stream?assistant_id=");
        urlBuilder.append(assistantId);
        urlBuilder.append("&stream_mode=messages-tuple&stream_mode=custom");
        urlBuilder.append("&if_not_exists=create");

        // 将 input 作为 URL 参数传递（需要 URL 编码）
        String inputJson = gson.toJson(input);
        urlBuilder.append("&input=");
        urlBuilder.append(Uri.encode(inputJson));

        return urlBuilder.toString();
    }

    /**
     * 构建请求体.
     */
    private JsonObject buildRequestBody(String message, List<FileType> files, String systemPrompt, String threadId) {
        JsonObject root = new JsonObject();

        // 构建消息数组
        JsonArray messages = new JsonArray();

        // 系统消息
        if (systemPrompt != null && !systemPrompt.isEmpty()) {
            JsonObject systemMsg = new JsonObject();
            systemMsg.addProperty("type", "system");
            systemMsg.addProperty("content", systemPrompt);
            messages.add(systemMsg);
        }

        // 用户消息
        JsonObject userMsg = new JsonObject();
        userMsg.addProperty("type", "human");

        // 内容块
        JsonArray contentBlocks = new JsonArray();

        // 文本内容
        JsonObject textBlock = new JsonObject();
        textBlock.addProperty("type", "text");
        textBlock.addProperty("text", message);
        contentBlocks.add(textBlock);

        // 文件内容
        if (files != null && !files.isEmpty()) {
            for (FileType file : files) {
                JsonObject fileBlock = new JsonObject();
                fileBlock.addProperty("type", "file");

                JsonObject fileData = new JsonObject();
                fileData.addProperty("type", file.getType());
                fileData.addProperty("data", file.getData());
                if (file.getMetadata() != null) {
                    JsonObject metadata = new JsonObject();
                    for (Map.Entry<String, Object> entry : file.getMetadata().entrySet()) {
                        metadata.addProperty(entry.getKey(), String.valueOf(entry.getValue()));
                    }
                    fileData.add("metadata", metadata);
                }
                contentBlocks.add(fileData);
            }
        }

        userMsg.add("content", contentBlocks);
        messages.add(userMsg);

        root.add("messages", messages);

        return root;
    }

    /**
     * 创建线程.
     *
     * @param threadId 线程 ID
     * @return 创建的线程信息
     */
    public Map<String, Object> createThread(String threadId) throws IOException {
        JsonObject body = new JsonObject();
        body.addProperty("thread_id", threadId);

        Request request = new Request.Builder()
                .url(url + "/threads")
                .post(RequestBody.create(gson.toJson(body), JSON))
                .build();

        try (Response response = httpClient.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                throw new IOException("Unexpected response: " + response);
            }
            String responseBody = response.body() != null ? response.body().string() : "";
            return parseJsonToMap(responseBody);
        }
    }

    /**
     * 获取线程.
     *
     * @param threadId 线程 ID
     * @return 线程信息
     */
    public Map<String, Object> getThread(String threadId) throws IOException {
        Request request = new Request.Builder()
                .url(url + "/threads/" + threadId)
                .get()
                .build();

        try (Response response = httpClient.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                throw new IOException("Unexpected response: " + response);
            }
            String responseBody = response.body() != null ? response.body().string() : "";
            return parseJsonToMap(responseBody);
        }
    }

    /**
     * 删除线程.
     *
     * @param threadId 线程 ID
     */
    public void deleteThread(String threadId) throws IOException {
        Request request = new Request.Builder()
                .url(url + "/threads/" + threadId)
                .delete()
                .build();

        try (Response response = httpClient.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                throw new IOException("Unexpected response: " + response);
            }
        }
    }

    /**
     * 解析 JSON 字符串为 Map.
     */
    @SuppressWarnings("unchecked")
    private Map<String, Object> parseJsonToMap(String json) {
        JsonElement element = gson.fromJson(json, JsonElement.class);
        return gson.fromJson(element, Map.class);
    }

    /**
     * 流式 WebSocket 监听器.
     */
    private class StreamingWebSocketListener extends WebSocketListener {

        private final StreamingEventHandlers handler;
        private final StringBuilder dataBuffer = new StringBuilder();
        private boolean isEventLine = true;
        private String currentEvent = null;

        public StreamingWebSocketListener(StreamingEventHandlers handler) {
            this.handler = handler;
        }

        @Override
        public void onOpen(WebSocket webSocket, Response response) {
            logger.info("WebSocket 连接已打开");
        }

        @Override
        public void onMessage(WebSocket webSocket, String text) {
            parseSseEvent(text);
        }

        @Override
        public void onClosing(WebSocket webSocket, int code, String reason) {
            logger.info("WebSocket 关闭: {} - {}", code, reason);
            webSocket.close(1000, null);

            // 通知主线程完成
            synchronized (StreamingClient.this) {
                StreamingClient.this.notifyAll();
            }
        }

        @Override
        public void onFailure(WebSocket webSocket, Throwable t, Response response) {
            logger.error("WebSocket 错误: {}", t.getMessage(), t);
            handler.onError(new RuntimeException("WebSocket error: " + t.getMessage(), t));

            // 通知主线程完成
            synchronized (StreamingClient.this) {
                StreamingClient.this.notifyAll();
            }
        }

        /**
         * 解析 SSE 事件.
         */
        private void parseSseEvent(String text) {
            String[] lines = text.split("\n");

            for (String line : lines) {
                if (line.startsWith("event:")) {
                    currentEvent = line.substring(6).trim();
                    isEventLine = true;
                } else if (line.startsWith("data:")) {
                    String data = line.substring(5).trim();
                    if (!data.isEmpty()) {
                        // 解析 JSON 数据
                        try {
                            Object parsedData = gson.fromJson(data, Object.class);
                            handler.receiveChunk(currentEvent, parsedData);
                        } catch (Exception e) {
                            logger.warn("解析 SSE 数据失败: {}", e.getMessage());
                        }
                    }
                    isEventLine = false;
                }
            }
        }
    }
}
