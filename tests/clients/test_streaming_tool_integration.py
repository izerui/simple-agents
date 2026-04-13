"""StreamingClient 流式工具调用集成测试."""

import asyncio
import json
import uuid

import pytest
from langgraph_sdk.schema import Config

from src.clients import MessageEvent, RunEvent, StreamingClient, ToolEvent
from src.clients.handlers import StreamingEventHandlers


class CaptureToolHandlers(StreamingEventHandlers):
    """收集流式正文和工具完成结果，便于断言。"""

    def __init__(self):
        self.tool_calls: list[dict] = []
        self.ai_chunks: list[str] = []
        self.errors: list[str] = []

    async def on_message_streaming(self, event: MessageEvent):
        if event.delta:
            self.ai_chunks.append(event.delta)

    async def on_tool_completed(self, event: ToolEvent):
        self.tool_calls.append(
            {
                "tool_id": event.tool_call_id,
                "tool_name": event.tool_name,
                "args": event.args_current,
                "content": event.result_current,
                "status": event.status,
            }
        )

    async def on_run_failed(self, event: RunEvent):
        self.errors.append(event.error or "run failed")


@pytest.mark.asyncio
class TestStreamingToolIntegration:
    """流式工具调用维度.

    关注：
    - 动态工具 schema 注入后能否被模型调用
    - 工具完成时能否拿到 args/result/status
    - assistant 正文是否仍然走流式事件
    """

    async def test_dynamic_schema_tool_end_to_end(self):
        host = "https://dev-dcca.hhstu.edu.cn/agent"
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

        await handler.consume(
            client.chat_stream(
                message=message,
                thread_id=thread_id,
                config=config,
                multitask_strategy="reject",
                stream_subgraphs=True,
                on_disconnect="cancel",
                on_completion="delete",
                durability="async",
                metadata={"name": "dynamic schema tool e2e"},
            )
        )

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
    asyncio.run(TestStreamingToolIntegration().test_dynamic_schema_tool_end_to_end())
