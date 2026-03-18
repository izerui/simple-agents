"""动态 schema 工具的 StreamingClient 端到端测试。"""

import asyncio
import json
import uuid

from langgraph_sdk.schema import Config

from src.clients import StreamingClient
from src.clients.handlers import StreamingEventHandlers


class CaptureToolHandlers(StreamingEventHandlers):
    """收集工具调用结果，便于断言。"""

    def __init__(self):
        super().__init__()
        self.tool_calls: list[dict] = []
        self.ai_chunks: list[str] = []
        self.errors: list[Exception] = []

    async def on_ai_message_chunk(
        self, content: str, is_chunk_start: bool = False, is_chunk_end: bool = False
    ):
        if content:
            self.ai_chunks.append(content)

    async def on_tool_call_start(self, tool_id: str, tool_name: str):
        return None

    async def on_tool_call_args_chunk(self, tool_id: str, args_chunk: str, is_chunk_start: bool = False):
        return None

    async def on_tool_result_chunk(self, tool_id: str, content: str, is_chunk_start: bool = False):
        return None

    async def on_tool_call_complete(
        self,
        tool_id: str,
        tool_name: str,
        args: str,
        content: str,
        status: str | None,
    ):
        self.tool_calls.append(
            {
                "tool_id": tool_id,
                "tool_name": tool_name,
                "args": args,
                "content": content,
                "status": status,
            }
        )

    async def on_custom(self, data: dict):
        return None

    async def on_error(self, error: Exception):
        self.errors.append(error)


async def test_dynamic_schema_tool_end_to_end():
    """验证通过 config.configurable.dynamic_tools 注入的工具可被模型调用并返回 echo 参数。"""
    host = "http://localhost:2024"
    assistant_id = "research"

    client = StreamingClient(url=host, assistant_id=assistant_id)
    handler = CaptureToolHandlers()
    thread_id = str(uuid.uuid4())

    config = Config(
        configurable={
            "dynamic_tools": [
                {
                    "name": "browser_click",
                    "description": "点击页面元素。当用户明确要求点击页面元素时调用。",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "selector": {
                                "type": "string",
                                "description": "要点击的 CSS selector",
                            },
                            "timeout": {
                                "type": "integer",
                                "description": "等待超时时间，单位毫秒",
                            },
                        },
                        "required": ["selector", "timeout"],
                    },
                }
            ]
        }
    )

    message = (
        "这是一个动态工具调用测试。"
        "你必须调用一次且仅一次工具 browser_click，"
        "参数 selector 设置为 '#submit'，timeout 设置为 1000。"
        "调用完成后只回复 OK。"
    )

    print(f"开始动态工具端到端测试: thread_id={thread_id}")
    print(f"用户输入: {message}")

    async for chunk in client.chat_stream(
        message=message,
        thread_id=thread_id,
        config=config,
        multitask_strategy="reject",
        stream_subgraphs=True,
        on_disconnect="cancel",
        on_completion="delete",
        durability="async",
        metadata={"name": "dynamic schema tool e2e"},
    ):
        await handler.receive_chunk(chunk)

    assert not handler.errors

    browser_click_calls = [call for call in handler.tool_calls if call["tool_name"] == "browser_click"]
    assert browser_click_calls, "模型没有调用动态注入的 browser_click 工具"

    call = browser_click_calls[0]
    assert call["status"] == "success"

    args = json.loads(call["args"])
    assert args == {"selector": "#submit", "timeout": 1000}

    result = json.loads(call["content"])
    assert result["ok"] is True
    assert result["tool"] == "browser_click"
    assert result["arguments"] == {"selector": "#submit", "timeout": 1000}

    ai_text = "".join(handler.ai_chunks)
    assert "OK" in ai_text

    print("\n" + "=" * 80)
    print("✅ 动态 schema 工具测试完成")
    print(f"工具调用次数: {len(browser_click_calls)}")
    print(f"工具参数: {args}")
    print(f"工具返回: {result}")
    print(f"AI 输出: {ai_text}")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_dynamic_schema_tool_end_to_end())
