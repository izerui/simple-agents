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


# 存储工具调用信息，用于匹配开始和结果
tool_calls_registry = {}


async def get_file_base64(file_path):
    import aiofiles
    async with aiofiles.open(file_path, 'rb') as f:
        return base64.b64encode(await f.read()).decode('utf-8')


async def output_stream_result(chunks, chunk_file=None):
    """
    处理流式输出结果 - messages-tuple 模式

    stream_mode: ["messages-tuple", "custom"]
    """
    global tool_calls_registry
    tool_calls_registry = {}  # 重置
    current_content = ''

    async for chunk in chunks:
        try:
            # 将 chunk 写入文件（如果提供了文件）
            if chunk_file:
                chunk_file.write(str(chunk) + "\n")
                chunk_file.flush()

            # messages-tuple 模式下，chunk 是 StreamPart 对象
            event_name = chunk.event if hasattr(chunk, 'event') else None
            data = chunk.data if hasattr(chunk, 'data') else None

            if event_name is None:
                continue

            # 处理自定义事件 (custom)
            if event_name == "custom":
                if isinstance(data, dict):
                    event_type = data.get('type', '')
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

            # 处理 messages-tuple 事件
            if event_name == "messages":
                if not isinstance(data, list) or len(data) < 2:
                    continue

                # data[0] 是消息内容，data[1] 是 metadata
                msg_list = data[0]

                if not isinstance(msg_list, list):
                    msg_list = [msg_list]

                for msg in msg_list:
                    msg_type = msg.get('type') if isinstance(msg, dict) else None

                    # 处理 AI 消息块 (AIMessageChunk) - 流式输出 + 工具调用
                    if msg_type == "AIMessageChunk":
                        content = msg.get('content', '')
                        tool_calls = msg.get('tool_calls', [])
                        tool_call_chunks = msg.get('tool_call_chunks', [])

                        # 输出文本内容
                        if content:
                            print(content, end='', flush=True)
                            current_content += content

                        # 处理 tool_calls - 工具调用开始（只处理有完整信息的）
                        if tool_calls:
                            for tc in tool_calls:
                                tool_name = tc.get('name', '')
                                tool_id = tc.get('id', '')

                                # 只有当 name 和 id 都不为空时才输出调用开始
                                if tool_name and tool_id:
                                    tool_calls_registry[tool_id] = {
                                        'name': tool_name,
                                        'args': '',
                                        'started': True
                                    }
                                    print(f"\n🔧 工具: {tool_name}")
                                    print(f"   ID: {tool_id}")
                                    print(f"📝 参数: ", end='', flush=True)

                        # 处理 tool_call_chunks - 工具参数流式输出
                        if tool_call_chunks:
                            for tcc in tool_call_chunks:
                                tcc_id = tcc.get('id', '')
                                args_chunk = tcc.get('args', '')

                                # 累加参数
                                if tcc_id and tcc_id in tool_calls_registry:
                                    tool_calls_registry[tcc_id]['args'] += args_chunk
                                elif args_chunk:
                                    # 没有找到匹配的 ID，尝试通过 name 查找
                                    name = tcc.get('name', '')
                                    for tid, info in tool_calls_registry.items():
                                        if info.get('name') == name:
                                            tool_calls_registry[tid]['args'] += args_chunk
                                            break

                                # 流式输出参数
                                if args_chunk:
                                    print(f"{args_chunk}", end='', flush=True)

                    # 处理工具执行结果 (tool) - 流式输出
                    elif msg_type == "tool":
                        tool_name = msg.get('name', 'unknown')
                        tool_content = msg.get('content', '')
                        tool_status = msg.get('status', None)
                        tool_call_id = msg.get('tool_call_id', '')

                        # 流式输出结果
                        print(f"\n✅ 结果: {tool_content}", end='', flush=True)

                        # 处理待办列表（完整结果时）
                        if tool_status == "success" and tool_name == "write_todos":
                            print("")  # 换行
                            todo_content = tool_content.replace("Updated todo list to", "").strip()
                            try:
                                todos = ast.literal_eval(todo_content)
                                print(f"\n📋 任务清单:")
                                for i, todo in enumerate(todos, 1):
                                    todo_item = todo.get('content', '')
                                    todo_status = todo.get('status', 'unknown')
                                    status_icon = "⏳" if todo_status == "in_progress" else (
                                        "✅" if todo_status == "completed" else "⭕")
                                    print(f"  {i}. [{status_icon}] {todo_item}")
                            except Exception as e:
                                print(f"❌ 解析待办列表失败: {e}")

                continue

        except Exception as e:
            print(f"\n❌ 输出结果出错: {e}")
            import traceback
            traceback.print_exc()

    if current_content:
        print(f'\n{current_content}')

    return current_content


async def search():
    # host = 'https://agent.schoopia.com'
    host = 'http://localhost:2024'

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

    input_data = {
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
        input=input_data,
        multitask_strategy='reject',
        stream_mode=[
            "messages-tuple",
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
