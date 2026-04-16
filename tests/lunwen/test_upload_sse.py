import asyncio
import base64
import os
import uuid
from urllib.parse import quote

import aiofiles
import requests
from langgraph_sdk import get_client
from langchain_core.messages import HumanMessage, SystemMessage


# 存储工具调用信息
tool_calls_registry = {}


async def get_file_base64(file_path):
    async with aiofiles.open(file_path, 'rb') as f:
        return base64.b64encode(await f.read()).decode('utf-8')


async def output_stream_result(chunks, chunk_file=None):
    """处理流式输出结果 - messages-tuple 模式"""
    global tool_calls_registry
    tool_calls_registry = {}
    current_content = ''
    last_tool_call_ended = False

    async for chunk in chunks:
        try:
            if chunk_file:
                chunk_file.write(str(chunk) + "\n")
                chunk_file.flush()

            event_name = chunk.event if hasattr(chunk, 'event') else None
            data = chunk.data if hasattr(chunk, 'data') else None

            if event_name is None:
                continue

            # 处理自定义事件 - 详细输出
            if event_name == "custom":
                print(f"\n{'='*60}")
                print(f"🔔 [CUSTOM EVENT] raw type: {type(data)}")
                if isinstance(data, dict):
                    import json as _json
                    print(f"   event_type: {data.get('type', 'N/A')}")
                    print(f"   完整数据:")
                    print(_json.dumps(data, ensure_ascii=False, indent=4))
                else:
                    print(f"   非dict数据: {data}")
                print(f"{'='*60}")
                continue

            # 处理 messages-tuple 事件
            if event_name == "messages":
                if not isinstance(data, list) or len(data) < 2:
                    continue

                msg_list = data[0]
                if not isinstance(msg_list, list):
                    msg_list = [msg_list]

                for msg in msg_list:
                    msg_type = msg.get('type') if isinstance(msg, dict) else None

                    if msg_type == "AIMessageChunk":
                        content = msg.get('content', '')
                        tool_calls = msg.get('tool_calls', [])
                        tool_call_chunks = msg.get('tool_call_chunks', [])

                        if content:
                            if last_tool_call_ended:
                                print("\n\n")
                                last_tool_call_ended = False
                            print(content, end='', flush=True)
                            current_content += content

                        if tool_calls:
                            for tc in tool_calls:
                                tool_name = tc.get('name', '')
                                tool_id = tc.get('id', '')
                                if tool_name and tool_id:
                                    tool_calls_registry[tool_id] = {
                                        'name': tool_name,
                                        'args': '',
                                        'started': True
                                    }
                                    print(f"\n🔧 工具: {tool_name}")
                                    print(f"   ID: {tool_id}")
                                    print(f"📝 参数: ", end='', flush=True)

                        if tool_call_chunks:
                            for tcc in tool_call_chunks:
                                tcc_id = tcc.get('id', '')
                                args_chunk = tcc.get('args', '')
                                if tcc_id and tcc_id in tool_calls_registry:
                                    tool_calls_registry[tcc_id]['args'] += args_chunk
                                elif args_chunk:
                                    name = tcc.get('name', '')
                                    for tid, info in tool_calls_registry.items():
                                        if info.get('name') == name:
                                            tool_calls_registry[tid]['args'] += args_chunk
                                            break
                                if args_chunk:
                                    print(f"{args_chunk}", end='', flush=True)

                    elif msg_type == "tool":
                        tool_content = msg.get('content', '')
                        print(f"\n✅ 结果: {tool_content}", end='', flush=True)
                        last_tool_call_ended = True

                continue

        except Exception as e:
            print(f"\n❌ 输出结果出错: {e}")
            import traceback
            traceback.print_exc()

    return current_content


async def main():
    host = 'http://localhost:2024'

    # 测试文件
    docx_path = "01_艺术学院_美术教育_余雪梅_20221304012021.docx"

    print(f"正在读取文件: {docx_path}")
    docx_content = await get_file_base64(docx_path)
    print(f"文件大小(base64): {len(docx_content)} 字符")

    user_message = """读取markdown格式论文，从专业角度评价该学生论文的以下方面：
1. 论文结构与逻辑：逻辑是否清晰、结构是否合理
2. 学术规范与表达：专业术语使用是否准确、表达是否清晰
3. 总结：整体评价和核心改进建议

注意：必须将分析结果写入到最终报告，报告路径写入：`deepthink/final_report.md`"""

    message = HumanMessage(content=[
        {"type": "text", "text": user_message},
        {"type": "file", "data": docx_content, "metadata": {"filename": docx_path}},
    ])

    input_data = {
        "messages": [
            SystemMessage(content="""你是一个本科毕业生的导师，以老师的角度进行分析，给出评价和改进建议。

## 输出报告格式要求
一、论文结构与逻辑
 1. 评价
 2. 改进建议
二、学术规范与表达
 1. 评价
 2. 改进建议
三、总结
 1. 评价
 2. 改进建议
四、总评
 评分(60-100):
 等级(优秀/良好/中等/合格/不合格):

## 注意：
必须将分析结果写入到最终报告，报告路径写入：`deepthink/final_report.md`"""),
            message
        ]
    }

    thread_id = str(uuid.uuid4())
    print("=" * 80)
    print(f"Thread ID: {thread_id}")
    print("=" * 80)

    client = get_client(url=host, api_key='')
    print(f"开始SSE流式对话...")

    chunks = client.runs.stream(
        thread_id=thread_id,
        assistant_id='research',
        input=input_data,
        multitask_strategy='reject',
        stream_mode=["messages-tuple", "custom"],
        if_not_exists='create',
        stream_subgraphs=True,
        on_disconnect='cancel',
        on_completion='keep',
    )

    result = await output_stream_result(chunks)

    print("\n" + "=" * 80)
    print("✅ SSE流式对话完成！")
    print(f"总输出长度: {len(result)} 字符")
    print("=" * 80)

    # 下载生成的报告
    download_url = f"{host}/webapp/download/{thread_id}?path={quote('deepthink/final_report.md')}"
    print(f"\n📥 下载报告: {download_url}")
    try:
        response = requests.get(download_url)
        if response.ok:
            report_content = response.content.decode('utf-8')
            print("\n" + "=" * 80)
            print("📄 报告内容:")
            print("=" * 80)
            print(report_content)
        else:
            print(f"❌ 下载失败，状态码: {response.status_code}, 响应: {response.text}")
    except Exception as e:
        print(f"❌ 下载报告出错: {e}")

    print("\n" + "=" * 80)
    print("✅ 全部测试完成！")
    print("=" * 80)


if __name__ == '__main__':
    asyncio.run(main())
