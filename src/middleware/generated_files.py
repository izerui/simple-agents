"""文件路径提取 Middleware

在 Agent 执行完成后，从消息中提取生成的文件路径，
通过 custom 事件发送给客户端。

通过调用 webapp 接口获取文件列表。
"""

import os
from typing import Any, TypedDict

import httpx
from langchain.agents.middleware import AgentMiddleware, AgentState


class GeneratedFilesState(TypedDict):
    """扩展的 Agent State，添加 generated_files 字段"""
    generated_files: list[str]


class GeneratedFilesMiddleware(AgentMiddleware):
    """提取 Agent 生成的文件路径并通过 custom 事件发送"""

    # 定义 state_schema，让 create_agent 自动收集并合并到 state
    state_schema = GeneratedFilesState

    # 测试模式：设置为 True 则总是发送测试文件
    TEST_MODE = False

    # webapp 接口地址
    EXTRACT_API_URL = os.getenv('EXTRACT_API_URL', 'http://localhost:2024')

    def __init__(self):
        """初始化"""
        super().__init__()
        self.tools = []

    @staticmethod
    def _normalize_content(content: Any) -> str:
        """将消息 content 归一化为纯文本字符串。"""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    text_parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        text_parts.append(text)
            return "".join(text_parts)
        return str(content)

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

        raw_content = last_message.content if hasattr(last_message, 'content') else str(last_message)
        content = self._normalize_content(raw_content)

        # 调用 webapp 接口获取文件列表
        file_paths = await self._extract_file_paths(content)

        if file_paths:
            # 发送 custom 事件
            runtime.stream_writer({
                "type": "generated_files",
                "content": file_paths
            })
            # 结合 line:16#GeneratedFilesState 持久化到 state
            return {"generated_files": file_paths}

        return None

    async def _extract_file_paths(self, content: str) -> list[str]:
        """调用 webapp 接口提取文件路径"""
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{self.EXTRACT_API_URL}/webapp/extract-file-paths",
                    json={"content": content}
                )
                response.raise_for_status()
                data = response.json()
                # 新 API 格式: {"success": true, "err_message": null, "data": [...]}
                if data.get("success"):
                    return data.get("data", []) or []
                else:
                    err_msg = data.get("err_message", "未知错误")
                    print(f"提取文件路径失败: {err_msg}")
                    return []
        except Exception as e:
            print(f"调用接口提取文件路径失败: {e}")
            return []
