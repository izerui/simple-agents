# -*- coding: utf-8 -*-
"""独立运行：带文件上传的 PDF 论文分析测试"""
import asyncio
import base64
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
    """运行带文件上传的 PDF 论文分析测试。"""
    thread_id = "test_pdf_analysis"
    
    # 用户问题
    user_message = """读取markdown格式论文，
        基于论文指导手册，从专业角度评价该学生论文的以下方面：
        1. 文献综述质量：是否全面、是否准确、是否有批判性思维
        2. 研究方法与实施：方法是否科学、是否可行、数据分析是否合理
        3. 论文结构与逻辑：逻辑是否清晰、结构是否合理
        4. 学术规范与表达：专业术语使用是否准确、表达是否清晰
        5. 总结：整体评价和核心改进建议"""
    
    # 读取并编码 PDF 文件
    pdf_path = project_root / "files/20210705041038_谷雷_冶金与材料学院_地理信息科.pdf"
    try:
        with open(pdf_path, 'rb') as f:
            pdf_content = base64.b64encode(f.read()).decode('utf-8')
    except FileNotFoundError:
        print(f"❌ 错误：PDF 文件不存在: {pdf_path}")
        return
    
    # 读取并编码图片文件
    md_path = project_root / "files/文山学院论文指导手册.md"
    try:
        with open(md_path, 'rb') as f:
            md_content = base64.b64encode(f.read()).decode('utf-8')
    except FileNotFoundError:
        print(f"❌ 错误：文件不存在: {md_path}")
        return
    
    # 打印测试标题
    print_header("带文件上传的 PDF 论文分析")
    
    # 显示用户问题和附件
    attachments = [
        {"type": "file", "data": pdf_content, "metadata": {"filename": pdf_path.name}},
        {"type": "image", "data": md_content, "metadata": {"name": md_path.name}}
    ]
    print_user_message(user_message, attachments)
    
    # 创建带有附件的消息
    message = HumanMessage(content=[
        {"type": "text", "text": user_message},
        {"type": "file", "data": pdf_content, "metadata": {"filename": pdf_path.name}, "mimeType": "application/pdf"},
        {"type": "file", "data": md_content, "metadata": {"filename": md_path.name}, "mimeType": "text/markdown"},
        # {"type": "image", "metadata": {"name": "跟单宝.png"}, "mime_type": "image/png", "data": image_content}
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
    
    # 打印测试完成标识
    print_footer("带文件上传的 PDF 论文分析")


if __name__ == "__main__":
    import time
    import shutil

    if Path('data').exists():
        shutil.rmtree('data', ignore_errors=True)

    start = time.time()
    asyncio.run(run_test())
    print(f"运行时间：{time.time() - start:.2f} 秒")