# -*- coding: utf-8 -*-
"""独立运行：工具调用功能测试"""
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
    """运行工具调用功能测试。"""
    thread_id = "test_tool_invocation"
    user_message = "创建一个文件名为 test_tool.md，内容为 'Tool Test'"
    
    # 打印测试标题
    print_header("工具调用功能")
    
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
    print_footer("工具调用功能")


if __name__ == "__main__":
    asyncio.run(run_test())