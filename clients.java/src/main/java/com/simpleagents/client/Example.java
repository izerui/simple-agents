package com.simpleagents.client;

import java.util.Collections;
import java.util.List;

/**
 * 示例程序.
 */
public class Example {

    public static void main(String[] args) throws Exception {
        // 创建客户端
        StreamingClient client = new StreamingClient(
                "http://localhost:2024",  // API 地址
                "your-api-key",           // API 密钥
                "research"                // 助手 ID
        );

        // 创建事件处理器
        StreamingEventHandlers handler = new SimpleStreamingEventHandlers();

        // 简单调用
        System.out.println("=== 简单调用 ===");
        client.chatStream("你好，请介绍一下你自己", handler);

        // 带系统提示
        System.out.println("\n=== 带系统提示 ===");
        client.chatStream("1+1等于几?", null, "你是一个数学助手", handler);

        // 带文件
        System.out.println("\n=== 带文件 ===");
        try {
            List<FileType> files = Collections.singletonList(
                    FileType.fromPath("/path/to/document.pdf")
            );
            client.chatStream("请分析这个文件", files, handler);
        } catch (Exception e) {
            System.err.println("文件加载失败: " + e.getMessage());
        }

        // 线程管理示例
        System.out.println("\n=== 线程管理 ===");
        String threadId = "test-thread-001";
        client.createThread(threadId);
        System.out.println("线程已创建: " + threadId);

        var threadInfo = client.getThread(threadId);
        System.out.println("线程信息: " + threadInfo);

        client.deleteThread(threadId);
        System.out.println("线程已删除: " + threadId);
    }
}
