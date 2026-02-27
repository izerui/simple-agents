import asyncio
import ast
import base64
import json
import os
import uuid
from urllib.parse import quote

import aiofiles
import aiohttp
import requests
from langchain_core.messages import HumanMessage, SystemMessage


async def get_file_base64(file_path):
    import aiofiles
    async with aiofiles.open(file_path, 'rb') as f:
        return base64.b64encode(await f.read()).decode('utf-8')


async def output_stream_result(chunks, chunk_file=None):
    """
    处理流式输出结果，参考 guidance.py 的实现
    """
    current_content = ''
    async for chunk in chunks:
        try:
            # 将 chunk 写入文件（如果提供了文件）
            if chunk_file:
                chunk_dict = {
                    'event': chunk.event if hasattr(chunk, 'event') else None,
                    'data': chunk.data if hasattr(chunk, 'data') else str(chunk)
                }
                chunk_file.write(json.dumps(chunk_dict, ensure_ascii=False) + "\n")
                chunk_file.flush()

            # 处理事件
            if hasattr(chunk, 'event'):
                event_name = chunk.event

                # 处理自定义事件 (custom)
                if event_name == "custom":
                    data = chunk.data if hasattr(chunk, 'data') else {}
                    event_type = data.get('type', '') if isinstance(data, dict) else ''

                    if event_type == "generated_files":
                        files = data.get('content', [])
                        if files:
                            print(f"\n📁 生成的文件:")
                            for f in files:
                                print(f"   - {f}")
                    else:
                        print(f"\n🔔 Custom 事件: {event_type}")
                        print(f"   数据: {data}")
                    continue

                # 添加事件类型调试信息
                if event_name not in ["messages/partial"]:  # 避免 partial 事件刷屏
                    print(f"[事件] {event_name}")

                if event_name == "messages/metadata":
                    if current_content and len(current_content) > 0:
                        print(f'\n{current_content}')
                        current_content = ''
                elif event_name == "messages/partial":
                    if isinstance(chunk.data, list):
                        msg = chunk.data[0]
                        content_list = msg.get('content', [])
                        if isinstance(content_list, list):
                            for content_item in content_list:
                                if content_item.get('type', None) == "text":
                                    current_content = content_item.get('text', None)
                                    break
                        elif isinstance(content_list, str):
                            current_content = content_list
                elif event_name == "messages/complete":
                    if isinstance(chunk.data, list):
                        msg = chunk.data[0]
                        # message type
                        msg_type = msg.get('type', None)
                        # tool name
                        name = msg.get('name', None)
                        # tool status
                        status = msg.get('status', None)
                        # tool content
                        content = msg.get('content', None)
                        # tool call id
                        tool_call_id = msg.get('tool_call_id', None)

                        # 打印工具调用信息
                        if msg_type == "tool":
                            print(f"\n🛠️ ===== 工具调用 =====")
                            print(f"工具名称: {name}")
                            print(f"工具状态: {status}")
                            print(f"工具内容: {content[:200]}..." if content and len(content) > 200 else f"工具内容: {content}")
                            print(f"============================\n")

                            # 处理待办列表
                            if name == "write_todos":
                                # 移除前缀并解析
                                todo_content = content.replace("Updated todo list to", "").strip()
                                try:
                                    todos = ast.literal_eval(todo_content)
                                    print(f"\n📋 ===== 任务清单 =====")
                                    for i, todo in enumerate(todos, 1):
                                        todo_item = todo.get('content', '')
                                        todo_status = todo.get('status', 'unknown')
                                        # 根据状态添加表情符号
                                        status_icon = "⏳" if todo_status == "in_progress" else (
                                            "✅" if todo_status == "completed" else "⭕")
                                        print(f"{i}. [{status_icon}] {todo_item}")
                                    print(f"============================\n")
                                except Exception as e:
                                    print(f"❌ 解析待办列表失败: {e}")
                        else:
                            print(f"\n🔍 ===== 调试信息 =====")
                            print(f"事件类型: {event_name}")
                            print(f"数据类型: {msg_type}")
                            print(f"数据内容: {chunk.data}")
                            print(f"============================\n")
        except Exception as e:
            print(f"❌ 输出结果出错: {e}")

    if current_content:
        print(f'\n{current_content}')

    return current_content


async def search():
    host = 'https://agent.schoopia.com'
    # host = 'http://localhost:2024'

    # 用户问题
    user_message = """读取markdown格式论文，
            基于论文指导手册，从专业角度评价该学生论文的以下方面：
            1. 文献综述质量：是否全面、是否准确、是否有批判性思维
            2. 研究方法与实施：方法是否科学、是否可行、数据分析是否合理
            3. 论文结构与逻辑：逻辑是否清晰、结构是否合理
            4. 学术规范与表达：专业术语使用是否准确、表达是否清晰
            5. 总结：整体评价和核心改进建议"""

    # 读取并编码 DOCX 文件
    docx_content = await get_file_base64("张卓群毕业论文3.docx")
    md_content = await get_file_base64("HELP.md")

    # 创建带有附件的消息
    message = HumanMessage(content=[
        {"type": "text", "text": user_message},
        {"type": "file", "data": docx_content, "metadata": {"filename": "1901180052张卓群毕业论文3.docx"}},
        {"type": "file", "data": md_content, "metadata": {"filename": "指导手册.md"}},
    ])

    input = {
        "messages": [
            SystemMessage(content="""# 你是一个本科毕业生的导师，以老师的角度进行分析，并给出评分和等级

## 评价和改进建议方面：

* 文献综述质量(从⽂献覆盖⾯、时效性、评述深度和格式规范层面进行评估。)
* 研究方法与实施(从⽅法适⽤性、数据可靠性和样本合理性层面进行评估。)
* 论文结构与逻辑(从结构规范性、逻辑连贯性和论证严密性层面进行评估。)
* 学术规范与表达(从语⾔表达、术语使⽤和格式符合性层面进行评估。)
* 总结(整合各维度结果，形成最终评价和优先级指导改进建议。)

## 风格:
以老师针对学生点评的的口吻回答，指明问题，给出方向，不需要给出具体的实施步骤。

## 研究内容:
质量、研究方法、结构、逻辑、规范、表达、等

## 评分、等级(需结合指导书给出相应的评分数值和等级):
1. 90-100: 优秀
2. 80-89.99: 良好
3. 70-79.99: 中等
4. 60-69.99: 合格
5. 60 分以下: 不合格

## 字数限制:
每个方面的评价和改进建议字符限制在400字以内

## 输出报告格式要求
结合论文格式分析结果和内容分析结果按下面五个方面分析并分别以评价和改进建议输出结论。
一、文献综述质量
  1. 评价
  2. 改进建议
二、研究方法与实施
  1. 评价
  2. 改进建议
三、论文结构与逻辑
  1. 评价
  2. 改进建议
四、学术规范与表达
  1. 评价
  2. 改进建议
五、总结
  1. 评价
  2. 改进建议
六、总评
  评分:
  等级:

## 注意：
必须将分析结果写入到最终报告，报告路径写入：`deepthink/final_report.md`"""),
            message
        ]
    }

    thread_id = str(uuid.uuid4())
    print("=" * 80)
    print(f"\n执行过程: https://chat-agent.schoopia.com/?threadId={thread_id}\n")
    print("=" * 80)

    # 生成唯一的文件名
    base_filename = "chunks.json"
    counter = 0
    while True:
        if counter == 0:
            filename = base_filename
        else:
            filename = f"chunks-{counter}.json"

        if not os.path.exists(filename):
            break
        counter += 1

    # 打开文件用于写入 chunks
    chunk_file = open(filename, "w", encoding="utf-8")

    # 参考 guidance.py 的 async_generate 函数
    # 创建独立的client实例，避免事件循环冲突
    local_client = get_client(url=host, api_key='')
    print(f"开始评价论文: bk: {thread_id}")
    chunks = local_client.runs.stream(
        thread_id=thread_id,
        assistant_id='research',
        input=input,
        multitask_strategy='reject',
        stream_mode=[
            "messages",
            "custom"
        ],
        if_not_exists='create',
        stream_subgraphs=True,
        on_disconnect='cancel',
        on_completion='keep',
        durability='async',
    )

    # 使用 output_stream_result 函数处理流式输出
    result = await output_stream_result(chunks, chunk_file)

    print(f'最终回答: {result}')

    print("\n" + "=" * 80)
    print("✅ 任务执行完成！")
    print("=" * 80)

    # 关闭 chunk 文件
    chunk_file.close()

    # 从 https://chat-agent.schoopia.com/threads/{thread_id}/download_report 网络地址下载markdown文件
    download_url = f"{host}/webapp/download/{thread_id}?path={quote('deepthink/final_report.md')}"
    print(f'下载报告: {download_url}')
    try:
        response = requests.get(download_url)
        if response.ok:
            content = response.content.decode('utf-8')
            print(content)
        else:
            print(f"❌ 下载失败，状态码: {response.status_code}")
    except Exception as e:
        print(f"❌ 发生未知错误: {e}")


    print("\n" + "=" * 80)
    print("✅ 任务执行完成！")
    print("=" * 80)


if __name__ == '__main__':
    from langgraph_sdk import get_client

    asyncio.run(search())