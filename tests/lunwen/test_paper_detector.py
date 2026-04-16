import asyncio
import base64
import json
import os
import uuid
from urllib.parse import quote

import aiofiles
import requests
from langgraph_sdk import get_client
from langchain_core.messages import HumanMessage, SystemMessage


# 存储工具调用信息
tool_calls_registry = {}
# 收集所有 custom events
custom_events = []
# 收集生成的文件路径
generated_files = []


async def get_file_base64(file_path):
    async with aiofiles.open(file_path, 'rb') as f:
        return base64.b64encode(await f.read()).decode('utf-8')


async def output_stream_result(chunks):
    """处理流式输出结果 - messages-tuple 模式"""
    global tool_calls_registry, custom_events, generated_files
    tool_calls_registry = {}
    custom_events = []
    generated_files = []
    current_content = ''
    last_tool_call_ended = False

    async for chunk in chunks:
        try:
            event_name = chunk.event if hasattr(chunk, 'event') else None
            data = chunk.data if hasattr(chunk, 'data') else None

            if event_name is None:
                continue

            # 处理自定义事件 - 详细输出
            if event_name == "custom":
                custom_events.append(data)
                print(f"\n{'='*60}")
                print(f"🔔 [CUSTOM EVENT]")
                if isinstance(data, dict):
                    event_type = data.get('type', 'N/A')
                    print(f"   event_type: {event_type}")
                    print(f"   完整数据:")
                    print(json.dumps(data, ensure_ascii=False, indent=4))
                    if event_type == "generated_files":
                        generated_files.extend(data.get('content', []))
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
                        tool_name = msg.get('name', 'unknown')
                        tool_content = msg.get('content', '')
                        # 工具结果太长时截断显示
                        display = tool_content[:200] + "..." if len(tool_content) > 200 else tool_content
                        print(f"\n✅ [{tool_name}] 结果: {display}", end='', flush=True)
                        last_tool_call_ended = True

                continue

        except Exception as e:
            print(f"\n❌ 输出结果出错: {e}")
            import traceback
            traceback.print_exc()

    return current_content


async def main():
    host = 'http://localhost:2024'
    output_dir = "结果"
    os.makedirs(output_dir, exist_ok=True)

    # 测试文件
    docx_path = "01_艺术学院_美术教育_余雪梅_20221304012021.docx"
    # 报告输出文件名（与论文同名，改为 .md）
    report_filename = os.path.splitext(docx_path)[0] + ".md"
    local_report_path = os.path.join(output_dir, report_filename)

    print(f"📄 论文文件: {docx_path}")
    print(f"📁 报告输出: {local_report_path}")

    print(f"正在读取文件...")
    docx_content = await get_file_base64(docx_path)
    print(f"文件大小(base64): {len(docx_content)} 字符")

    user_message = f"""/skills/paper-detector

请对这篇论文进行查重检测和AI生成内容检测，生成完整的检测报告。"""

    message = HumanMessage(content=[
        {"type": "text", "text": user_message},
        {"type": "file", "data": docx_content, "metadata": {"filename": docx_path}},
    ])

    input_data = {
        "messages": [message]
    }

    thread_id = str(uuid.uuid4())
    print("=" * 80)
    print(f"Thread ID: {thread_id}")
    print("=" * 80)

    client = get_client(url=host, api_key='')
    print(f"开始SSE流式对话 (paper-detector)...")

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

    print("\n\n" + "=" * 80)
    print("✅ SSE流式对话完成！")
    print(f"总输出长度: {len(result)} 字符")
    print("=" * 80)

    # 汇总 custom events
    print(f"\n📊 共收到 {len(custom_events)} 个 Custom Events:")
    for i, evt in enumerate(custom_events):
        if isinstance(evt, dict):
            print(f"   {i+1}. type={evt.get('type', 'N/A')}")
        else:
            print(f"   {i+1}. {evt}")

    print(f"\n📁 生成的文件: {generated_files}")

    # 下载报告
    if generated_files:
        for remote_path in generated_files:
            download_url = f"{host}/webapp/download/{thread_id}?path={quote(remote_path.lstrip('/'))}"
            print(f"\n📥 下载: {download_url}")
            try:
                response = requests.get(download_url)
                if response.ok:
                    report_content = response.content.decode('utf-8')
                    # 保存到本地
                    with open(local_report_path, 'w', encoding='utf-8') as f:
                        f.write(report_content)
                    print(f"✅ 报告已保存到: {local_report_path}")
                    print(f"   文件大小: {len(report_content)} 字符")
                    # 打印前2000字符预览
                    print("\n" + "-" * 60)
                    print("📄 报告预览 (前2000字符):")
                    print("-" * 60)
                    print(report_content[:2000])
                    if len(report_content) > 2000:
                        print(f"\n... (还有 {len(report_content) - 2000} 字符)")
                else:
                    print(f"❌ 下载失败，状态码: {response.status_code}, 响应: {response.text}")
            except Exception as e:
                print(f"❌ 下载报告出错: {e}")
    else:
        # 尝试默认路径下载
        for try_path in ['deepthink/final_report.md', 'final_report.md']:
            download_url = f"{host}/webapp/download/{thread_id}?path={quote(try_path)}"
            print(f"\n📥 尝试下载: {download_url}")
            try:
                response = requests.get(download_url)
                if response.ok:
                    report_content = response.content.decode('utf-8')
                    with open(local_report_path, 'w', encoding='utf-8') as f:
                        f.write(report_content)
                    print(f"✅ 报告已保存到: {local_report_path}")
                    print(f"   文件大小: {len(report_content)} 字符")
                    print("\n" + "-" * 60)
                    print("📄 报告预览 (前2000字符):")
                    print("-" * 60)
                    print(report_content[:2000])
                    break
                else:
                    print(f"   未找到 ({response.status_code})")
            except Exception as e:
                print(f"   出错: {e}")

    print("\n" + "=" * 80)
    print("✅ 全部测试完成！")
    print("=" * 80)


if __name__ == '__main__':
    asyncio.run(main())
