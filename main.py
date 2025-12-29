# -*- coding: utf-8 -*-
"""运行 agent 并在对话结束后自动清理沙箱目录

这个模块展示了如何使用 BackendFactory 实现每个对话独立的沙箱路径，
并在对话结束后自动清理临时文件。
"""

import uuid
import asyncio
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

# 在所有其他导入之前加载环境变量
load_dotenv(dotenv_path='.env', verbose=True)

from agent import agent
from sandbox_backend import sandbox_manager, _current_thread_id


async def run_agent_with_cleanup(user_message: str = None):
    """
    运行 agent 并在结束后自动清理沙箱目录
    
    Args:
        user_message: 用户输入的消息，如果不提供则使用默认消息
    """
    # 为每次对话生成唯一的 thread_id
    thread_id = str(uuid.uuid4())
    
    if user_message is None:
        user_message = "读取文件内容帮我汇总后，生成一个新的汇总文件。"
    
    print(f"{'=' * 80}")
    print(f"🚀 开始对话 (thread_id: {thread_id})")
    print(f"📝 用户消息: {user_message}")
    print(f"{'=' * 80}")
    
    inputs = {
        "messages": [HumanMessage(content=user_message)]
    }

    config = {
        "configurable": {
            "thread_id": thread_id,  # ← 这个 ID 决定了沙箱路径
            "recursion_limit": 100
        },
    }

    try:
        print("\n--- 开始执行 (使用 astream_events 监控节点) ---")

        # 上传 files 目录的内容到沙箱
        print("\n📤 正在上传文件到沙箱...")
        sandbox_manager.upload_files_to_sandbox(thread_id, "./files/")

        # 设置 thread_id 到 ContextVar，这样 backend_factory 可以正确获取
        token = _current_thread_id.set(thread_id)

        # 执行 agent
        async for event in agent.astream_events(inputs, version="v1", config=config):
            kind = event["event"]

            # 监控节点执行
            if kind == "on_chain_end":
                node_name = event["name"]
                node_output = event["data"].get("output")
                print(f"✅ 节点 [{node_name}] 执行完毕")
                if node_output and len(str(node_output)) > 100:
                    print(f"   输出摘要: {str(node_output)[:100]}...\n")

            # 监控 Token 级别 (打字机效果)
            elif kind == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content:
                    print(content, end="", flush=True)

        print("\n\n--- 执行结束 ---")
        
        # 显示会话信息
        session_info = sandbox_manager.get_session_info(thread_id)
        print(f"\n📊 会话统计:")
        print(f"   会话目录: {session_info['session_dir']}")
        print(f"   文件数量: {session_info['file_count']}")
        
    finally:
        # ✅ 关键：对话结束后自动清理沙箱
        # 使用 finally 块确保即使发生异常也会清理
        print(f"\n🧹 正在清理沙箱 (thread_id: {thread_id})")
        sandbox_manager.cleanup_session(thread_id)
        print("✨ 清理完成！")
        
        # 清除 ContextVar 中的 thread_id
        _current_thread_id.reset(token)


async def run_multiple_conversations():
    """
    演示多个独立的对话，每个都有独立的沙箱路径
    """
    print("=" * 80)
    print("📝 演示：多个独立对话，每个都有独立的沙箱路径")
    print("=" * 80)
    print()
    
    # 定义多个独立的对话任务
    conversations = [
        "请列出当前目录的所有文件",
        "创建一个名为 test.md 的文件并写入 'Hello Sandbox!'",
        "读取 help.md 文件的内容"
    ]
    
    for i, user_message in enumerate(conversations, 1):
        print(f"\n{'=' * 80}")
        print(f"对话 {i}/{len(conversations)}: {user_message}")
        print(f"{'=' * 80}")
        
        thread_id = str(uuid.uuid4())
        inputs = {"messages": [HumanMessage(content=user_message)]}
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}
        
        try:
            # 显示会话目录
            print(f"\n📁 沙箱目录: ./sandbox_sessions/{thread_id}/")
            
            # 上传 files 目录的内容到沙箱
            print("\n📤 正在上传文件到沙箱...")
            sandbox_manager.upload_files_to_sandbox(thread_id, "./files/")
            
            # 设置 thread_id 到 ContextVar
            token = _current_thread_id.set(thread_id)
            
            # 执行 agent
            async for event in agent.astream_events(inputs, version="v1", config=config):
                kind = event["event"]
                
                if kind == "on_chat_model_stream":
                    content = event["data"]["chunk"].content
                    if content:
                        print(content, end="", flush=True)
                        
            # 显示会话统计
            session_info = sandbox_manager.get_session_info(thread_id)
            print(f"\n\n📊 会话统计: {session_info['file_count']} 个文件")
                        
        finally:
            # 清理当前对话的沙箱
            print(f"\n🧹 清理对话 {i} 的沙箱...")
            sandbox_manager.cleanup_session(thread_id)
            
            # 清除 ContextVar 中的 thread_id
            _current_thread_id.reset(token)
            
            print(f"✅ 对话 {i} 完成\n")
    
    print("=" * 80)
    print("🎉 所有对话完成！")
    print("=" * 80)


async def run_with_user_input():
    """
    交互式对话模式，用户可以输入多次消息
    每次消息使用相同的 thread_id（连续对话）
    """
    print("=" * 80)
    print("💬 交互式对话模式")
    print("=" * 80)
    print("提示: 输入 'quit' 或 'exit' 退出\n")
    
    thread_id = str(uuid.uuid4())
    print(f"📁 会话 ID: {thread_id}")
    print(f"📁 沙箱目录: ./sandbox_sessions/{thread_id}/\n")
    
    try:
        # 上传 files 目录的内容到沙箱
        print("\n📤 正在上传文件到沙箱...")
        sandbox_manager.upload_files_to_sandbox(thread_id, "./files/")
        
        # 设置 thread_id 到 ContextVar（整个会话期间保持）
        token = _current_thread_id.set(thread_id)
        
        while True:
            # 获取用户输入
            user_input = input("用户: ").strip()
            
            # 检查退出命令
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 再见！")
                break
            
            if not user_input:
                print("⚠️  请输入消息或输入 'quit' 退出\n")
                continue
            
            # 执行 agent
            print("\nAgent: ", end="", flush=True)
            
            inputs = {"messages": [HumanMessage(content=user_input)]}
            config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 100}
            
            async for event in agent.astream_events(inputs, version="v1", config=config):
                kind = event["event"]
                
                if kind == "on_chat_model_stream":
                    content = event["data"]["chunk"].content
                    if content:
                        print(content, end="", flush=True)
            
            print("\n")
            
            # 显示当前会话的文件数量
            session_info = sandbox_manager.get_session_info(thread_id)
            if session_info['file_count'] > 0:
                print(f"📊 当前沙箱中有 {session_info['file_count']} 个文件\n")
            else:
                print()
    
    finally:
        # 清理会话
        print(f"\n🧹 清理会话沙箱...")
        sandbox_manager.cleanup_session(thread_id)
        
        # 清除 ContextVar 中的 thread_id
        _current_thread_id.reset(token)
        
        print("✨ 清理完成！")


# 主函数
if __name__ == "__main__":
    import sys
    
    # 根据命令行参数选择运行模式
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        
        if mode == "multiple":
            # 模式 1: 运行多个独立对话
            asyncio.run(run_multiple_conversations())
        elif mode == "interactive":
            # 模式 2: 交互式对话模式
            asyncio.run(run_with_user_input())
        else:
            # 模式 3: 单次对话（自定义消息）
            message = " ".join(sys.argv[1:])
            asyncio.run(run_agent_with_cleanup(message))
    else:
        # 默认模式: 运行单次对话（使用默认消息）
        asyncio.run(run_agent_with_cleanup())