package com.simpleagents.client;

import java.util.Map;

/**
 * 简单的事件处理器实现.
 *
 * 使用方式:
 * <pre>
 * StreamingClient client = new StreamingClient("http://localhost:2024", "assistant_id");
 * StreamingEventHandlers handler = new SimpleStreamingEventHandlers();
 * client.chatStream("你好", handler);
 * </pre>
 *
 * 该实现将事件输出到标准输出，可继承并覆盖方法来实现自定义处理。
 */
public class SimpleStreamingEventHandlers extends StreamingEventHandlers {

    @Override
    public void onAiMessageChunk(String content, boolean isChunkStart) {
        if (content != null && !content.isEmpty()) {
            if (isChunkStart) {
                System.out.print("\n\n");
            }
            System.out.print(content);
            System.out.flush();
        }
    }

    @Override
    public void onToolCallStart(String toolId, String toolName) {
        System.out.println("工具: " + toolName);
        System.out.println("ID: " + toolId);
    }

    @Override
    public void onToolCallArgsChunk(String toolId, String argsChunk, boolean isChunkStart) {
        if (argsChunk != null && !argsChunk.isEmpty()) {
            if (isChunkStart) {
                System.out.println();
            }
            System.out.print(argsChunk);
            System.out.flush();
        }
    }

    @Override
    public void onToolResultChunk(String toolId, String content, boolean isChunkStart) {
        if (content != null && !content.isEmpty()) {
            if (isChunkStart) {
                System.out.println();
            }
            System.out.print(content);
            System.out.flush();
        }
    }

    @Override
    public void onToolCallComplete(String toolId, String toolName, String args, String content, String status) {
        System.out.print("\n\n🔧 ===== 工具调用完成 =====");
        System.out.println();
        System.out.println("工具: " + toolName);
        System.out.println("ID: " + toolId);
        if (status != null) {
            System.out.println("状态: " + status);
        }
        // 截断显示
        String displayArgs = args.length() > 50 ? args.substring(0, 50) + "..." : args;
        String displayContent = content.length() > 50 ? content.substring(0, 50) + "..." : content;
        System.out.println("参数: " + displayArgs);
        System.out.println("结果: " + displayContent);
        System.out.println("===========================\n");
    }

    @Override
    public void onCustom(Map<String, Object> data) {
        System.out.print("\n🔔 自定义事件");
        System.out.println();
        System.out.println("   数据: " + data);
    }

    @Override
    public void onError(Exception error) {
        System.out.print("\n❌ 错误: " + error.getMessage());
        System.out.println();
    }
}
