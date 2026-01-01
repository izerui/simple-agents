"""Tests for agent workflow."""

import base64
import asyncio
import uuid
from pathlib import Path
from typing import Any
import json

import pytest
import pytest_asyncio
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from graph import agent


def detailed_output_handler(event):
    """优化的事件输出处理器，优先流式输出（打字机效果）。"""
    kind = event["event"]

    # 1. 流式输出（打字机效果）- 优先处理
    if kind == "on_chat_model_stream":
        chunk = event["data"]["chunk"]
        # 使用 content_blocks 属性（更可靠）
        if hasattr(chunk, "content_blocks"):
            for block in chunk.content_blocks:
                if block["type"] == "text":
                    # 实时流式输出文本
                    print(block["text"], end="", flush=True)
                elif block["type"] == "reasoning":
                    # AI 思考过程
                    print(f"\n💭 {block['reasoning']}")
        else:
            # 降级处理
            if hasattr(chunk, "content"):
                print(chunk.content, end="", flush=True)

    # 2. 流式输出结束
    elif kind == "on_chat_model_end":
        # 流式输出结束后换行
        print("", flush=True)

    # 3. 显示工具调用（增强透明度）
    elif kind == "on_tool_start":
        tool_name = event["name"]
        tool_input = event["data"].get("input", {})
        print(f"\n\n🔧 工具调用: {tool_name}")
        if tool_input:
            # 简洁显示工具参数
            try:
                if isinstance(tool_input, dict):
                    params = json.dumps(tool_input, ensure_ascii=False, indent=2)
                    print(f"📥 参数:\n{params}")
                else:
                    print(f"📥 参数: {tool_input}")
            except:
                print(f"📥 参数: {tool_input}")

    # 4. 显示工具执行结果
    elif kind == "on_tool_end":
        tool_name = event["name"]
        tool_output = event["data"].get("output", "")
        print(f"✅ 工具 {tool_name} 执行完成")
        # 显示结果摘要（如果结果太长）
        if tool_output and len(str(tool_output)) > 200:
            print(f"📤 结果: {str(tool_output)[:200]}...")
        elif tool_output:
            print(f"📤 结果: {tool_output}")

    # 5. 错误处理
    elif kind.endswith("_error"):
        error = event["data"].get("error")
        print(f"\n❌ 出错: {error}")
        if event.get("name"):
            print(f"   发生在: {event['name']}")


class TestAgent:
    """Test suite for agent workflow."""

    @pytest_asyncio.fixture
    async def run_agent_with_output(self):
        """通用辅助方法：运行 agent 并自动输出详细过程（流式输出）。"""
        async def _run(inputs, config, title=None):
            """运行 agent 并实时流式输出详细过程。"""
            if title:
                print(f"\n\n{'🔹'*40}")
                print(f"测试：{title}")
                print(f"{'🔹'*40}")
            
            # 显示用户问题
            messages = inputs.get("messages", [])
            if messages and len(messages) > 0:
                msg = messages[0]
                if isinstance(msg, dict):
                    content = msg.get("content", "")
                elif hasattr(msg, "content"):
                    content = str(msg.content)
                else:
                    content = str(msg)
                
                # 检查是否是结构化消息
                if isinstance(content, list):
                    for item in content:
                        if item.get("type") == "text":
                            print(f"\n{'='*80}")
                            print(f"👤 用户问题: {item.get('text')}")
                            print(f"{'='*80}")
                        elif item.get("type") == "file":
                            print(f"📎 文件上传: {item.get('metadata', {}).get('filename', 'unknown')}")
                        elif item.get("type") == "image":
                            print(f"🖼️  图片上传: {item.get('metadata', {}).get('name', 'unknown')}")
                else:
                    print(f"\n{'='*80}")
                    print(f"👤 用户问题: {content}")
                    print(f"{'='*80}")
            
            # 实时流式处理事件，同时收集事件用于断言
            events = []
            async for event in agent.astream_events(inputs, version="v2", config=config):
                # 立即处理并输出事件（实时流式）
                detailed_output_handler(event)
                # 收集事件用于后续断言
                events.append(event)
            
            if title:
                print(f"\n\n{'✅'*40}")
                print(f"{title} 完成")
                print(f"{'✅'*40}")
            
            return events
        
        return _run

    @pytest.fixture
    def pdf_path(self):
        """Get the path to test PDF file."""
        return Path("files/论文.pdf")

    @pytest.fixture
    def image_path(self):
        """Get the path to test image file."""
        return Path("files/跟单宝.png")

    @pytest_asyncio.fixture
    async def pdf_content_base64(self, pdf_path):
        """Read and encode PDF file to base64."""
        try:
            import aiofiles
            async with aiofiles.open(pdf_path, mode='rb') as f:
                file_content = await f.read()
                return base64.b64encode(file_content).decode('utf-8')
        except FileNotFoundError:
            pytest.skip(f"测试文件不存在: {pdf_path}")

    @pytest_asyncio.fixture
    async def image_content_base64(self, image_path):
        """Read and encode image file to base64."""
        try:
            import aiofiles
            async with aiofiles.open(image_path, mode='rb') as f:
                file_content = await f.read()
                return base64.b64encode(file_content).decode('utf-8')
        except FileNotFoundError:
            pytest.skip(f"测试文件不存在: {image_path}")

    @pytest.mark.asyncio
    async def test_simple_file_list(self, run_agent_with_output):
        """测试简单的文件列表查询。"""
        thread_id = "test_simple_list"
        user_message = "列出根目录文件"

        inputs = {"messages": [HumanMessage(content=user_message)]}
        config = RunnableConfig(
            configurable={
                "thread_id": thread_id,
                "tool_timeout": 30.0
            },
            recursion_limit=500,
        )

        events = await run_agent_with_output(inputs, config, "简单的文件列表查询")
        
        # 验证有事件返回
        assert len(events) > 0, "应该有事件返回"

        # 验证没有错误
        error_events = [e for e in events if e["event"].endswith("_error")]
        assert len(error_events) == 0, f"不应该有错误: {error_events}"

    @pytest.mark.asyncio
    async def test_pdf_to_markdown_conversion(self, run_agent_with_output):
        """测试 PDF 转 Markdown 转换功能。"""
        thread_id = "test_pdf_conversion"
        user_message = "请将 files/论文.pdf 转换为 Markdown 格式"

        inputs = {"messages": [HumanMessage(content=user_message)]}
        config = RunnableConfig(
            configurable={
                "thread_id": thread_id,
                "tool_timeout": 60.0
            },
            recursion_limit=500,
        )

        events = await run_agent_with_output(inputs, config, "PDF 转 Markdown 转换")
        
        # 验证有事件返回
        assert len(events) > 0, "应该有事件返回"

        # 验证没有错误
        error_events = [e for e in events if e["event"].endswith("_error")]
        assert len(error_events) == 0, f"不应该有错误: {error_events}"

    @pytest.mark.asyncio
    async def test_pdf_analysis_with_file_upload(self, run_agent_with_output, pdf_content_base64, image_content_base64):
        """测试带文件上传的 PDF 论文分析。"""
        thread_id = "test_pdf_analysis"
        user_message = """先将pdf论文转换成markdown格式，然后读取markdown格式论文，
        基于论文指导手册，从专业角度评价该学生论文的以下方面：
        1. 文献综述质量：是否全面、是否准确、是否有批判性思维
        2. 研究方法与实施：方法是否科学、是否可行、数据分析是否合理
        3. 论文结构与逻辑：逻辑是否清晰、结构是否合理
        4. 学术规范与表达：专业术语使用是否准确、表达是否清晰
        5. 总结：整体评价和核心改进建议"""

        message = HumanMessage(content=[
            {"type": "text", "text": user_message},
            {"type": "file", "data": pdf_content_base64, "metadata": {"filename": "1901180052张卓群毕业论文3.pdf"}, "mimeType": "application/pdf"},
            {"type": "image", "metadata": {"name": "跟单宝.png"}, "mime_type": "image/png", "data": image_content_base64}
        ])

        inputs = {"messages": [message]}
        config = RunnableConfig(
            configurable={
                "thread_id": thread_id,
                "tool_timeout": 300.0
            },
            recursion_limit=500,
        )

        events = await run_agent_with_output(inputs, config, "带文件上传的 PDF 论文分析")
        
        # 验证有事件返回
        assert len(events) > 0, "应该有事件返回"

        # 验证没有错误
        error_events = [e for e in events if e["event"].endswith("_error")]
        assert len(error_events) == 0, f"不应该有错误: {error_events}"

        # 验证有聊天模型输出
        chat_model_events = [e for e in events if e["event"] == "on_chat_model_end"]
        assert len(chat_model_events) > 0, "应该有聊天模型输出"

    @pytest.mark.asyncio
    async def test_multiple_conversations(self, run_agent_with_output):
        """测试多个独立对话。"""
        conversations = [
            "列出当前目录的所有文件",
            "创建一个名为 test.md 的文件并写入 'Hello Test!'",
        ]

        for i, user_message in enumerate(conversations, 1):
            thread_id = f"test_multi_conversation_{i}"
            inputs = {"messages": [HumanMessage(content=user_message)]}
            config = RunnableConfig(
                configurable={
                    "thread_id": thread_id,
                    "tool_timeout": 30.0
                },
                recursion_limit=500,
            )

            events = await run_agent_with_output(inputs, config, f"独立对话 {i}/{len(conversations)}")
            
            # 验证有事件返回
            assert len(events) > 0, f"对话 {i} 应该有事件返回"

            # 验证没有错误
            error_events = [e for e in events if e["event"].endswith("_error")]
            assert len(error_events) == 0, f"对话 {i} 不应该有错误: {error_events}"

    @pytest.mark.asyncio
    async def test_conversation_with_turns(self, run_agent_with_output):
        """测试多轮对话。"""
        thread_id = "test_conversation_turns"

        # 第一轮对话
        user_message_1 = "创建一个名为 test_conversation.md 的文件，内容为 '第一轮对话'"
        inputs_1 = {"messages": [HumanMessage(content=user_message_1)]}
        config = RunnableConfig(
            configurable={
                "thread_id": thread_id,
                "tool_timeout": 30.0
            },
            recursion_limit=500,
        )

        events_1 = await run_agent_with_output(inputs_1, config, "第一轮对话 (创建文件)")
        
        assert len(events_1) > 0, "第一轮对话应该有事件返回"
        error_events_1 = [e for e in events_1 if e["event"].endswith("_error")]
        assert len(error_events_1) == 0, f"第一轮对话不应该有错误: {error_events_1}"

        # 第二轮对话
        user_message_2 = "读取 test_conversation.md 文件的内容"
        inputs_2 = {"messages": [HumanMessage(content=user_message_2)]}
        # 使用相同的 thread_id 实现多轮对话
        events_2 = await run_agent_with_output(inputs_2, config, "第二轮对话 (读取文件)")
        
        assert len(events_2) > 0, "第二轮对话应该有事件返回"
        error_events_2 = [e for e in events_2 if e["event"].endswith("_error")]
        assert len(error_events_2) == 0, f"第二轮对话不应该有错误: {error_events_2}"

    @pytest.mark.asyncio
    async def test_tool_invocation(self, run_agent_with_output):
        """测试工具调用功能。"""
        thread_id = "test_tool_invocation"
        user_message = "创建一个文件名为 test_tool.md，内容为 'Tool Test'"

        inputs = {"messages": [HumanMessage(content=user_message)]}
        config = RunnableConfig(
            configurable={
                "thread_id": thread_id,
                "tool_timeout": 30.0
            },
            recursion_limit=500,
        )

        events = await run_agent_with_output(inputs, config, "工具调用功能")
        
        # 验证有工具调用事件
        tool_events = [e for e in events if e["event"] == "on_tool_start"]
        assert len(tool_events) > 0, "应该有工具调用"

        # 验证没有错误
        error_events = [e for e in events if e["event"].endswith("_error")]
        assert len(error_events) == 0, f"不应该有错误: {error_events}"

    @pytest.mark.asyncio
    async def test_error_handling_nonexistent_file(self, run_agent_with_output):
        """测试错误处理 - 读取不存在的文件。"""
        thread_id = "test_error_handling"
        user_message = "读取一个不存在的文件 nonexistent_file.txt"

        inputs = {"messages": [HumanMessage(content=user_message)]}
        config = RunnableConfig(
            configurable={
                "thread_id": thread_id,
                "tool_timeout": 30.0
            },
            recursion_limit=500,
        )

        events = await run_agent_with_output(inputs, config, "错误处理：读取不存在的文件")
        
        # 验证有事件返回
        assert len(events) > 0, "应该有事件返回"

        # 验证最终有输出（错误处理应该让 agent 继续运行）
        chat_model_events = [e for e in events if e["event"] == "on_chat_model_end"]
        assert len(chat_model_events) > 0, "agent 应该处理错误并继续运行"

    @pytest.mark.asyncio
    async def test_markdown_file_operations(self, run_agent_with_output):
        """测试 Markdown 文件操作。"""
        thread_id = str(uuid.uuid4())

        # 创建 Markdown 文件
        create_message = "创建一个文件 test.md，内容为 '# 标题\\n\\n这是一个测试段落'"
        inputs_1 = {"messages": [HumanMessage(content=create_message)]}
        config = RunnableConfig(
            configurable={
                "thread_id": thread_id,
                "tool_timeout": 30.0
            },
            recursion_limit=500,
        )

        events_1 = await run_agent_with_output(inputs_1, config, "步骤 1: 创建 Markdown 文件")
        assert len(events_1) > 0, "创建文件应该有事件返回"

        # 读取 Markdown 文件
        read_message = "读取 test.md 文件的内容"
        inputs_2 = {"messages": [HumanMessage(content=read_message)]}
        events_2 = await run_agent_with_output(inputs_2, config, "步骤 2: 读取 Markdown 文件")
        assert len(events_2) > 0, "读取文件应该有事件返回"

        # 验证没有错误
        all_events = events_1 + events_2
        error_events = [e for e in all_events if e["event"].endswith("_error")]
        assert len(error_events) == 0, f"不应该有错误: {error_events}"
        
        print(f"\n\n{'🎉'*40}")
        print(f"测试完成！所有步骤执行成功")
        print(f"{'🎉'*40}\n")