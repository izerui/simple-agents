# -*- coding: utf-8 -*-
"""独立运行：错误处理测试 - 读取不存在的文件"""
import asyncio
from pathlib import Path
import sys
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

# 加载环境变量并添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
load_dotenv(dotenv_path=project_root / '.env')

from src.graph import agent
from src.tests.agents.output_handler import output_handler, print_header, print_user_message, print_footer


async def run_test():
    """运行错误处理测试 - 读取不存在的文件。"""
    thread_id = "test_error_handling"
    user_message = "读取一个不存在的文件 nonexistent_file.txt"
    
    # 打印测试标题
    print_header("错误处理：读取不存在的文件")
    
    # 显示用户问题
    print_user_message(user_message)
    
    inputs = {"messages": [HumanMessage(content=user_message)]}
    config = RunnableConfig(
        configurable={
            "thread_id": thread_id,
            "tool_timeout": 30.0
        },
        recursion_limit=500,
    )
    
    # 执行 agent（流式输出）
    async for event in agent.astream_events(inputs, version="v2", config=config):
        output_handler(event)
    
    # 打印测试完成标识
    print_footer("错误处理测试")


if __name__ == "__main__":
    import time
    import shutil

    if Path('data').exists():
        shutil.rmtree('data', ignore_errors=True)

    start = time.time()
    asyncio.run(run_test())
    print(f"运行时间：{time.time() - start:.2f} 秒")