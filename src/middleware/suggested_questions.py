"""建议问题生成 Middleware

在 Agent 执行完成后，通过调用 webapp 接口生成建议问题，
通过 custom 事件发送给客户端。
"""

import os
import re
import logging
from typing import Any, TypedDict

import httpx
from langchain.agents.middleware import AgentMiddleware, AgentState

logger = logging.getLogger(__name__)


class SuggestedQuestionsState(TypedDict):
    """扩展的 Agent State，添加 suggested_questions 字段"""
    suggested_questions: list[str]


class SuggestedQuestionsMiddleware(AgentMiddleware):
    """生成建议问题并通过 custom 事件发送"""

    # 定义 state_schema，让 create_agent 自动收集并合并到 state
    state_schema = SuggestedQuestionsState

    # webapp 接口地址
    EXTRACT_API_URL = os.getenv('EXTRACT_API_URL', 'http://localhost:2024')

    def __init__(self):
        """初始化"""
        super().__init__()

    @staticmethod
    def _compact_system_prompt(system_prompt: str) -> str:
        """压缩 system prompt，只保留对建议问题生成真正有帮助的用户偏好。"""
        if not system_prompt:
            return ""

        text = system_prompt.strip()

        # 优先提取用户附加偏好段，避免把完整默认系统提示再次送入小任务。
        marker = "[调用方附加系统要求]"
        if marker in text:
            text = text.split(marker, 1)[-1].strip()

        # 轻量压缩空白和长度，保留可读性。
        text = re.sub(r"\s+", " ", text)
        return text[:600]

    async def aafter_agent(self, state: AgentState, runtime: Any) -> dict | None:
        """在 Agent 执行完成后生成建议问题"""
        messages = state.get("messages", [])
        if not messages:
            return None

        # 获取 system prompt
        system_prompt = self._compact_system_prompt(state.get("user_system_message", ""))

        # 获取最后5条消息，区分 AI 和 HUMAN
        recent_messages = messages[-5:] if len(messages) > 5 else messages
        human_message_parts = []

        for msg in recent_messages:
            msg_type = getattr(msg, 'type', None)
            content = msg.content if hasattr(msg, 'content') else str(msg)
            if msg_type == 'ai':
                human_message_parts.append(f"AI: {content}")
            elif msg_type == 'human':
                human_message_parts.append(f"用户: {content}")

        if not human_message_parts:
            return None

        human_message = "\n".join(human_message_parts)

        # 调用 webapp 接口生成建议问题
        questions = await self._generate_suggested_questions(system_prompt, human_message)

        if questions:
            # 发送 custom 事件
            runtime.stream_writer({
                "type": "suggested_questions",
                "content": questions
            })
            return {"suggested_questions": questions}

        return None

    async def _generate_suggested_questions(self, system_prompt: str, human_message: str) -> list[str]:
        """调用 webapp 接口生成建议问题"""
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{self.EXTRACT_API_URL}/webapp/generate-suggested-questions",
                    json={
                        "system_prompt": system_prompt,
                        "human_message": human_message
                    }
                )
                response.raise_for_status()
                data = response.json()
                # 新 API 格式: {"success": true, "err_message": null, "data": [...]}
                if data.get("success"):
                    return data.get("data", []) or []
                else:
                    err_msg = data.get("err_message", "未知错误")
                    logger.warning("生成建议问题失败: %s", err_msg)
                    return []
        except Exception as e:
            logger.warning("调用接口生成建议问题失败: %r", e)
            return []
