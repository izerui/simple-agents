# -*- coding: utf-8 -*-
"""独立运行：多轮对话测试"""
import asyncio
from pathlib import Path
import sys
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

# 加载环境变量并添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
load_dotenv(dotenv_path=project_root / '.env')

from graph import agent
from tests.agents.output_handler import output_handler, print_header, print_user_message, print_footer


async def run_test():
    """运行多轮对话测试。"""
    thread_id = "test_conversation_turns"

    print("\n" + "=" * 80)
    print("💬 多轮对话测试")
    print("=" * 80)

    # 第一轮对话
    print_header("第一轮对话（创建文件）")
    user_message_1 = "创建一个名为 test_conversation.md 的文件，内容为 '第一轮对话'"
    print_user_message(user_message_1)

    inputs_1 = {"messages": [HumanMessage(content=user_message_1)]}
    config = RunnableConfig(
        configurable={
            "thread_id": thread_id,
            "tool_timeout": 30.0
        },
        recursion_limit=500,
    )

    # 执行 agent（流式输出）
    async for event in agent.astream_events(inputs_1, version="v2", config=config):
        output_handler(event)

    print_footer("第一轮对话")

    # 第二轮对话（使用相同的 thread_id 保持上下文）
    print_header("第二轮对话（读取文件）")
    user_message_2 = "读取 test_conversation.md 文件的内容"
    print_user_message(user_message_2)

    inputs_2 = {"messages": [HumanMessage(content=user_message_2)]}

    # 执行 agent（流式输出）
    async for event in agent.astream_events(inputs_2, version="v2", config=config):
        output_handler(event)

    print_footer("第二轮对话")

    print("=" * 80)
    print("🎉 多轮对话测试完成！")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(run_test())