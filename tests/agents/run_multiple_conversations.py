# -*- coding: utf-8 -*-
"""独立运行：多个独立对话测试"""
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
    """运行多个独立对话测试。"""
    # 定义多个独立的对话任务
    conversations = [
        "列出当前目录的所有文件",
        "创建一个名为 test.md 的文件并写入 'Hello Test!'",
    ]

    print("\n" + "=" * 80)
    print("📝 演示：多个独立对话，每个都有独立的沙箱路径")
    print("=" * 80)

    for i, user_message in enumerate(conversations, 1):
        thread_id = f"test_multi_conversation_{i}"
        
        # 为每个对话打印标题
        print_header(f"独立对话 {i}/{len(conversations)}")
        
        # 显示用户问题
        print_user_message(user_message)
        
        inputs = {"messages": [HumanMessage(content=user_message)]}
        config = RunnableConfig(
            configurable={
                "thread_id": thread_id,  # ← 这个 ID 决定了沙箱路径
                "tool_timeout": 30.0
            },
            recursion_limit=500,
        )
        
        # 执行 agent（流式输出）
        async for event in agent.astream_events(inputs, version="v2", config=config):
            output_handler(event)
        
        # 打印每个对话的完成标识
        print_footer(f"对话 {i}")

    print("=" * 80)
    print("🎉 所有对话完成！")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(run_test())