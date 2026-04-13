"""clients 协议层单元测试.

这个文件只测“原始 chunk -> 规范化事件”的解析逻辑，
不依赖真实后端，适合验证流式顺序和工具参数关联。
"""

from types import SimpleNamespace

from src.clients.client import _EventParser


class TestStreamingProtocolUnit:
    """流式协议解析维度.

    关注：
    - 事件顺序是否稳定
    - 工具参数是否正确累积
    - 匿名工具参数是否会在身份稳定后补发
    """

    def test_event_parser_emits_message_tool_and_run_events_in_order(self):
        parser = _EventParser(thread_id="thread-1")
        chunks = [
            SimpleNamespace(event="metadata", data={"run_id": "run-1"}),
            SimpleNamespace(
                event="messages",
                data=[
                    [
                        {
                            "type": "AIMessageChunk",
                            "id": "msg-1",
                            "content": "你",
                            "tool_calls": [],
                            "tool_call_chunks": [],
                            "chunk_position": None,
                        }
                    ],
                    {"run_id": "run-1"},
                ],
            ),
            SimpleNamespace(
                event="messages",
                data=[
                    [
                        {
                            "type": "AIMessageChunk",
                            "id": "msg-1",
                            "content": "",
                            "tool_calls": [
                                {"name": "ls", "id": "call-1", "args": {}, "index": 0}
                            ],
                            "tool_call_chunks": [
                                {"name": "ls", "id": "call-1", "args": '{"path": "/"}', "index": 0}
                            ],
                            "chunk_position": "last",
                        }
                    ],
                    {"run_id": "run-1"},
                ],
            ),
            SimpleNamespace(
                event="messages",
                data=[
                    [
                        {
                            "type": "tool",
                            "name": "ls",
                            "tool_call_id": "call-1",
                            "content": '["a"]',
                            "status": "success",
                        }
                    ],
                    {"run_id": "run-1"},
                ],
            ),
        ]

        events = []
        for chunk in chunks:
            events.extend(parser.process_chunk(chunk))

        assert [(event.type, getattr(event, "status", None)) for event in events] == [
            ("run", "started"),
            ("message", "streaming"),
            ("tool", "pending"),
            ("tool", "streaming_args"),
            ("message", "completed"),
            ("tool", "running"),
            ("tool", "streaming_result"),
            ("tool", "success"),
        ]

        message_event = events[1]
        assert message_event.message_id == "msg-1"
        assert message_event.delta == "你"
        assert message_event.current == "你"

        tool_args_event = events[3]
        assert tool_args_event.tool_name == "ls"
        assert tool_args_event.tool_call_id == "call-1"
        assert tool_args_event.args_current == '{"path": "/"}'

    def test_event_parser_replays_anonymous_tool_args_after_identity_is_stable(self):
        parser = _EventParser(thread_id="thread-1")
        chunks = [
            SimpleNamespace(event="metadata", data={"run_id": "run-1"}),
            SimpleNamespace(
                event="messages",
                data=[
                    [
                        {
                            "type": "AIMessageChunk",
                            "id": "msg-1",
                            "content": "",
                            "tool_calls": [{"name": "ls", "id": "call-1", "args": {}}],
                            "tool_call_chunks": [{"name": "", "id": "", "args": '{"path": "/"}', "index": 0}],
                            "chunk_position": "last",
                        }
                    ],
                    {"run_id": "run-1"},
                ],
            ),
        ]

        events = []
        for chunk in chunks:
            events.extend(parser.process_chunk(chunk))

        assert [(event.type, getattr(event, "status", None)) for event in events] == [
            ("run", "started"),
            ("tool", "pending"),
            ("tool", "streaming_args"),
            ("message", "completed"),
        ]
        tool_args_event = events[2]
        assert tool_args_event.tool_name == "ls"
        assert tool_args_event.tool_call_id == "call-1"
        assert tool_args_event.args_current == '{"path": "/"}'
