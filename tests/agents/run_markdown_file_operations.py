# -*- coding: utf-8 -*-
"""独立运行：Markdown 文件操作测试"""
import asyncio
from pathlib import Path
import sys
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

# 加载环境变量并添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
load_dotenv(dotenv_path=project_root / '.env')

from src.graph import agent
from tests.agents.output_handler import output_handler, print_header, print_user_message, print_footer


async def run_test():
    """运行 Markdown 文件操作测试。"""
    thread_id = "test_markdown_operations"

    print("\n" + "=" * 80)
    print("📝 Markdown 文件操作测试")
    print("=" * 80)

    # 步骤 1: 创建 Markdown 文件
    print_header("步骤 1: 创建 Markdown 文件")
    create_message = "创建一个文件 test.md，内容为 '# 标题\\n\\n这是一个测试段落'"
    print_user_message(create_message)

    inputs_1 = {"messages": [HumanMessage(content=create_message)]}
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

    print_footer("创建 Markdown 文件")

    # 步骤 2: 读取 Markdown 文件
    print_header("步骤 2: 读取 Markdown 文件")
    read_message = "读取 test.md 文件的内容"
    print_user_message(read_message)

    inputs_2 = {"messages": [HumanMessage(content=read_message)]}

    # 使用相同的 thread_id 实现连续对话
    async for event in agent.astream_events(inputs_2, version="v2", config=config):
        output_handler(event)

    print_footer("读取 Markdown 文件")

    print("=" * 80)
    print("🎉 Markdown 文件操作测试完成！")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    import time
    import shutil

    if Path('data').exists():
        shutil.rmtree('data', ignore_errors=True)

    start = time.time()
    asyncio.run(run_test())
    print(f"运行时间：{time.time() - start:.2f} 秒")