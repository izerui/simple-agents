"""使用 StreamingClient SDK 的测试函数."""

import asyncio
import os
import uuid

from src.clients import StreamingClient, SimpleEventHandlers

# 测试文件目录
TEST_DIR = os.path.dirname(os.path.abspath(__file__))


async def test_paper_evaluation():
    """测试: 论文评价."""
    host = "http://localhost:2024"
    assistant_id = "research"

    user_message = """读取markdown格式论文，基于论文指导手册，从专业角度评价该学生论文,写入到最终报告文件中。"""

    system_prompt = """# 你是一个本科毕业生的导师，以老师的角度进行分析"""

    # 支持直接传入文件路径
    files = [
        os.path.join(TEST_DIR, "张卓群毕业论文3.docx"),
        os.path.join(TEST_DIR, "HELP.md"),
    ]

    thread_id = str(uuid.uuid4())
    client = StreamingClient(url=host, assistant_id=assistant_id)
    handler = SimpleEventHandlers()

    print(f"用户输入: {user_message[:50]}...")

    async for chunk in client.chat_stream(
        message=user_message,
        files=files,
        system_prompt=system_prompt,
        thread_id=thread_id,
        multitask_strategy="reject",
        stream_subgraphs=True,
        on_disconnect="cancel",
        on_completion="keep",
        durability="async",
        metadata={"user_id": "user001", "name": "张卓群的论文评价"},
    ):
        await handler.receive_chunk(chunk)

    print("\n" + "=" * 80)
    print("✅ 任务执行完成！")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_paper_evaluation())
