"""文件路径提取 Middleware

在 Agent 执行完成后，从消息中提取生成的文件路径，
通过 custom 事件发送给客户端。

通过调用 webapp 接口获取文件列表。
"""

import os
from typing import Any

import httpx
from langchain.agents.middleware import AgentMiddleware, AgentState


class GeneratedFilesMiddleware(AgentMiddleware):
    """提取 Agent 生成的文件路径并通过 custom 事件发送"""

    # 测试模式：设置为 True 则总是发送测试文件
    TEST_MODE = False

    # webapp 接口地址
    EXTRACT_API_URL = os.getenv('EXTRACT_API_URL', 'http://localhost:2024')

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

        # 获取最后一条 AI 消息
        last_message = None
        for msg in reversed(messages):
            if hasattr(msg, 'type') and msg.type == 'ai':
                last_message = msg
                break
            elif hasattr(msg, 'type') and msg.type == 'system':
                continue
            else:
                last_message = msg
                break

        if not last_message:
            return None

        content = last_message.content if hasattr(last_message, 'content') else str(last_message)

        # 调用 webapp 接口获取文件列表
        file_paths = await self._extract_file_paths(content)

        if file_paths:
            # 发送 custom 事件
            runtime.stream_writer({
                "type": "generated_files",
                "content": file_paths
            })

        return None

    async def _extract_file_paths(self, content: str) -> list[str]:
        """调用 webapp 接口提取文件路径"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.EXTRACT_API_URL}/webapp/extract-file-paths",
                    json={"content": content}
                )
                response.raise_for_status()
                data = response.json()
                return data.get('files', [])
        except Exception as e:
            print(f"调用接口提取文件路径失败: {e}")
            return []
