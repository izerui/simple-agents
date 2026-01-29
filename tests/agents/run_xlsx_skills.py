# -*- coding: utf-8 -*-
import asyncio
import base64
from pathlib import Path
import sys
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

# 加载环境变量并添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
load_dotenv(dotenv_path=project_root / '.env')

from src.graph import agent
from tests.agents.output_handler import output_handler, print_header, print_user_message, print_footer


def read_file(file_path: str):
    try:
        with open(file_path, 'rb') as f:
            file_content = base64.b64encode(f.read()).decode('utf-8')
            return file_content
    except FileNotFoundError:
        print(f"❌ 错误：文件不存在: {file_path}")
        return None


async def run_test():
    thread_id = "test_xlsx_analysis"

    if Path(project_root / "data" / "sandbox_sessions" / thread_id).exists():
        shutil.rmtree(Path(project_root / "data" / "sandbox_sessions" / thread_id))

    # 用户问题
    user_message = """生成一个测试xlsx文件，添加汇总图表。"""
    

    # 创建带有附件的消息
    message = HumanMessage(content=[
        {"type": "text", "text": user_message},
    ])
    
    inputs = {"messages": [message]}
    config = RunnableConfig(
        configurable={
            "thread_id": thread_id,
            "tool_timeout": 300.0
        },
        recursion_limit=500,
    )
    
    # 执行 agent（流式输出）
    async for event in agent.astream_events(inputs, version="v2", config=config):
        output_handler(event)
    
if __name__ == "__main__":
    import time
    import shutil

    if Path('data').exists():
        shutil.rmtree('data', ignore_errors=True)

    start = time.time()
    asyncio.run(run_test())
    print(f"运行时间：{time.time() - start:.2f} 秒")