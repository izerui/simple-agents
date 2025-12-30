# -*- coding: utf-8 -*-
"""运行 agent 并在对话结束后自动清理沙箱目录

这个模块展示了如何使用 BackendFactory 实现每个对话独立的沙箱路径，
并在对话结束后自动清理临时文件。
"""

import uuid
import asyncio
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from utils import format_messages

# 在所有其他导入之前加载环境变量
load_dotenv(dotenv_path='.env', verbose=True)

from agent import agent

async def run_agent_with_cleanup(user_message: str):
    """
    运行 agent 并在结束后自动清理沙箱目录

    Args:
        user_message: 用户输入的消息，如果不提供则使用默认消息
    """
    # 为每次对话生成唯一的 thread_id
    thread_id = str(uuid.uuid4())

    print(f"{'=' * 80}")
    print(f"🚀 开始对话 (thread_id: {thread_id})")
    print(f"📝 用户消息: {user_message}")
    print(f"{'=' * 80}")

    inputs = {
        "messages": [HumanMessage(content=user_message)]
    }

    format_messages([HumanMessage(content=user_message)])

    config = RunnableConfig(
        configurable={
            "thread_id": thread_id, # ← 这个 ID 决定了沙箱路径
            "tool_timeout": 30.0
        },
        recursion_limit=500,
    )

    try:
        # 执行 agent
        async for event in agent.astream_events(inputs, version="v1", config=config):
            output_handler( event)

        print("\n\n--- 执行结束 ---")

    finally:
        # ✅ 关键：对话结束后自动清理沙箱
        # 使用 finally 块确保即使发生异常也会清理
        pass


async def run_multiple_conversations(conversations: list[str]):
    """
    演示多个独立的对话，每个都有独立的沙箱路径
    """
    print("=" * 80)
    print("📝 演示：多个独立对话，每个都有独立的沙箱路径")
    print("=" * 80)
    print()

    for i, user_message in enumerate(conversations, 1):
        print(f"\n{'=' * 80}")
        print(f"对话 {i}/{len(conversations)}: {user_message}")
        print(f"{'=' * 80}")

        thread_id = str(uuid.uuid4())
        inputs = {"messages": [HumanMessage(content=user_message)]}
        config = RunnableConfig(
            configurable={
                "thread_id": thread_id,  # ← 这个 ID 决定了沙箱路径
                "tool_timeout": 30.0
            },
            recursion_limit=500,
        )
        try:
            # 执行 agent
            async for event in agent.astream_events(inputs, version="v1", config=config):
                output_handler( event)
        finally:
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

    try:
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
            config = RunnableConfig(
                configurable={
                    "thread_id": thread_id,  # ← 这个 ID 决定了沙箱路径
                    "tool_timeout": 30.0
                },
                recursion_limit=500,
            )

            async for event in agent.astream_events(inputs, version="v1", config=config):
                output_handler( event)

            print("\n")

    finally:
        pass


def output_handler(event):
    kind = event["event"]

    # 监控 Token 级别 (打字机效果)
    if kind == "on_chat_model_stream":
        chunk = event["data"]["chunk"]
        # 使用 content_blocks 属性（更可靠）
        if hasattr(chunk, "content_blocks"):
            for block in chunk.content_blocks:
                if block["type"] == "text":
                    print(block["text"], end="", flush=True)
                elif block["type"] == "reasoning":
                    print(f"\n💭 {block['reasoning']}")
                # elif block["type"] == "tool_call_chunk":
                #     print(f"\n🔧 工具调用: {block.get('name')}")
        else:
            # 降级处理
            print(chunk.content, end="", flush=True)

    # 监控 Token 流结束
    elif kind == "on_chat_model_end":
        # 流式输出结束后换行
        print("", flush=True)

    # 2. 显示工具调用（增强透明度）
    # elif kind == "on_tool_start":
    #     print(f"\n🔧 正在调用: {event['name']}")

    # 3. 显示执行步骤
    elif kind == "on_chain_end":
        node_name = event["name"]
        node_output = event["data"].get("output")
        # print(f"✅ 节点 [{node_name}] 执行完毕")
        if node_output and len(str(node_output)) > 100:
            # print(f"   输出摘要: {str(node_output)[:100]}...\n")
            pass

        # 4. 错误处理
    elif kind.endswith("_error"):
        print(f"\n❌ 出错: {event['data'].get('error')}")

# 主函数
if __name__ == "__main__":
    import sys

    # 模式 1: 运行多个独立对话
    # 定义多个独立的对话任务
    # conversations = [
    #     "请列出当前目录的所有文件",
    #     "创建一个名为 test.md 的文件并写入 'Hello Sandbox!'",
    #     "读取 help.md 文件的内容"
    # ]
    # asyncio.run(run_multiple_conversations(conversations))

    # 模式 2: 交互式对话模式
    # asyncio.run(run_with_user_input())

    # 模式 3: 单次对话（自定义消息）
    message = """基于论文指导手册，从专业角度评价该学生论文的以下方面：
1. 文献综述质量：是否全面、是否准确、是否有批判性思维
2. 研究方法与实施：方法是否科学、是否可行、数据分析是否合理
3. 论文结构与逻辑：逻辑是否清晰、结构是否合理
4. 学术规范与表达：专业术语使用是否准确、表达是否清晰
5. 总结：整体评价和核心改进建议, 结论针对五个方面各自给出评价和改进建议，每个模块建议字数不超过300字。并依托指导手册针对该论文进行打分。"""
    asyncio.run(run_agent_with_cleanup(message))
