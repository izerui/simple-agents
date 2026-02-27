"""文件路径提取 Middleware

在 Agent 执行完成后，从消息中提取生成的文件路径，
通过 custom 事件发送给客户端。

通过拦截 write_file 工具调用来记录文件路径。
"""

import re
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState


class GeneratedFilesMiddleware(AgentMiddleware):
    """提取 Agent 生成的文件路径并通过 custom 事件发送"""

    # 测试模式：设置为 True 则总是发送测试文件
    TEST_MODE = False

    def __init__(self):
        """初始化"""
        super().__init__()
        self.tools = []

    async def aafter_agent(self, state: AgentState, runtime: Any) -> dict | None:
        """在 Agent 执行完成后提取文件路径"""
        messages = state.get("messages", [])
        if not messages:
            return None

        # 测试模式：总是发送测试文件
        if self.TEST_MODE:
            runtime.stream_writer({
                "type": "generated_files",
                "content": [
                    "deepthink/test_report.md",
                    "deepthink/final_report.md",
                    "output/summary.json"
                ]
            })
            return None

        # 从消息中提取 write_file 工具调用的文件路径
        file_paths = self._extract_write_file_paths(messages)

        if file_paths:
            # 发送 custom 事件
            runtime.stream_writer({
                "type": "generated_files",
                "content": file_paths
            })

        return None

    def _extract_write_file_paths(self, messages: list) -> list[str]:
        """从消息中提取 write_file 工具调用的文件路径"""
        file_paths = []
        seen_paths = set()

        for msg in messages:
            # 从 AIMessage 的 tool_calls 中提取 file_path
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    if tool_call.get('name') == 'write_file':
                        args = tool_call.get('args', {})
                        # args 可能是 dict 或字符串
                        if isinstance(args, dict):
                            file_path = args.get('file_path')
                        else:
                            # 如果是字符串，尝试解析
                            try:
                                import json
                                args_dict = json.loads(args) if isinstance(args, str) else {}
                                file_path = args_dict.get('file_path')
                            except Exception:
                                file_path = None

                        if file_path and file_path not in seen_paths:
                            seen_paths.add(file_path)
                            file_paths.append(file_path)

            # 也从 ToolMessage 的返回内容中提取（作为备用）
            if hasattr(msg, 'type') and msg.type == 'tool':
                if hasattr(msg, 'name') and msg.name == 'write_file':
                    content = msg.content if hasattr(msg, 'content') else ''
                    # 匹配 "Created file {path}" 或 "Updated file {path}"
                    match = re.search(r'(?:Created|Updated) file (.+)', content)
                    if match:
                        path = match.group(1).strip()
                        if path and path not in seen_paths:
                            seen_paths.add(path)
                            file_paths.append(path)

        return file_paths
