# -*- coding: utf-8 -*-
"""共享的事件输出处理器模块

提供流式输出支持，可用于所有独立的测试运行文件。
"""
import json


def show_agent_info(event):
    """显示智能体信息（智能体名称和 thread_id）。
    
    Args:
        event: LangGraph 事件对象
        
    功能：
        - 显示智能体名称和 thread_id
    """
    thread_id = event.get("metadata", {}).get("thread_id", "unknown")
    tags = event.get("tags", [])
    metadata = event.get("metadata", {})
    agent_name = metadata.get("agent_name") or metadata.get("name") or "AI"

    # 使用 run_id 去重，确保每个消息只显示一次
    print(f"\n🤖 智能体: {agent_name}")
    print(f"🧵 Thread ID: {thread_id}")
    print(f"🧵 Tags: {tags}")


def output_handler(event):
    """事件输出处理器（流式输出优先）。
    
    Args:
        event: LangGraph 事件对象
        
    功能：
        - 显示智能体名称
        - 实时流式输出 AI 回复（打字机效果）
        - 显示工具调用及参数
        - 显示工具执行结果
        - 显示错误信息
    """
    kind = event["event"]
    
    # 1. 流式输出（打字机效果）- 优先处理
    if kind == "on_chat_model_stream":
        # 显示智能体信息
        # show_agent_info(event)
        chunk = event["data"]["chunk"]
        # 使用 content_blocks 属性（更可靠）
        if hasattr(chunk, "content_blocks"):
            for block in chunk.content_blocks:
                if block["type"] == "text":
                    # 实时流式输出文本
                    print(block["text"], end="", flush=True)
                elif block["type"] == "reasoning":
                    # AI 思考过程
                    print(f"\n💭 {block['reasoning']}")
        else:
            # 降级处理
            if hasattr(chunk, "content"):
                print(chunk.content, end="", flush=True)
    
    # 2. 流式输出结束
    elif kind == "on_chat_model_end":
        # 流式输出结束后换行
        print("", flush=True)
    
    # 3. 显示工具调用（增强透明度）
    elif kind == "on_tool_start":
        # 显示智能体信息
        show_agent_info(event)
        tool_name = event["name"]
        tool_input = event["data"].get("input", {})
        print(f"🔧 工具调用: {tool_name}")
        if tool_input:
            # 简洁显示工具参数
            try:
                if isinstance(tool_input, dict):
                    params = json.dumps(tool_input, ensure_ascii=False, indent=2)
                    print(f"📥 参数:\n{params}")
                else:
                    print(f"📥 参数: {tool_input}")
            except:
                print(f"📥 参数: {tool_input}")
    
    # 4. 显示工具执行结果
    elif kind == "on_tool_end":
        # 显示智能体信息
        show_agent_info(event)
        tool_name = event["name"]
        tool_output = event["data"].get("output", "")
        print(f"✅ 工具 {tool_name} 执行完成")
        # 显示结果摘要（如果结果太长）
        if tool_output and len(str(tool_output)) > 200:
            print(f"📤 结果: {str(tool_output)[:200]}...")
        elif tool_output:
            print(f"📤 结果: {tool_output}")
    
    # 5. 错误处理
    elif kind.endswith("_error"):
        # 显示智能体信息
        show_agent_info(event)
        error = event["data"].get("error")
        print(f"❌ 出错: {error}")
        if event.get("name"):
            print(f"   发生在: {event['name']}")


def print_header(title):
    """打印测试标题。
    
    Args:
        title: 测试标题字符串
    """
    print(f"\n{'🔹'*40}")
    print(f"测试：{title}")
    print(f"{'🔹'*40}")


def print_user_message(message, attachments=None):
    """打印用户问题。
    
    Args:
        message: 用户消息字符串
        attachments: 可选的附件信息列表（用于文件上传）
    """
    print(f"\n{'='*80}")
    print(f"👤 用户问题: {message}")
    print(f"{'='*80}")
    
    if attachments:
        for attachment in attachments:
            if attachment.get("type") == "file":
                print(f"📎 文件上传: {attachment.get('metadata', {}).get('filename', 'unknown')}")
            elif attachment.get("type") == "image":
                print(f"🖼️  图片上传: {attachment.get('metadata', {}).get('name', 'unknown')}")


def print_footer(title=None):
    """打印测试完成标识。
    
    Args:
        title: 可选的测试标题，用于标识哪个测试完成
    """
    print(f"\n{'✅'*40}")
    if title:
        print(f"{title} 完成")
    else:
        print(f"测试完成！")
    print(f"{'✅'*40}\n")