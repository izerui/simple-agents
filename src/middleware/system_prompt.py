"""自定义 system prompt 处理中间件。

用于从输入消息中提取 system message，替换默认的 agent prompt。
这样可以支持在 API 请求中传递自定义 system prompt。
"""
import logging
from typing import Any, TypedDict

from langchain.agents.middleware.types import AgentMiddleware, AgentState, ContextT, ModelRequest, ModelResponse, ResponseT
from langchain_core.messages import AnyMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)

USER_SYSTEM_PROMPT_MARKER = "[调用方附加系统要求]"
USER_SYSTEM_PROMPT_PREFIX = f"""\n\n{USER_SYSTEM_PROMPT_MARKER}
以下内容来自调用方在本次请求中额外传入的 system prompt。
请将其视为对默认系统提示的补充或覆盖，并按以下规则执行：
1. 始终优先遵守更高层级的系统、安全、工具和运行时约束。
2. 若与默认系统提示不冲突，则同时遵守默认系统提示与以下附加要求。
3. 若与默认系统提示冲突，则以以下附加要求为准。
4. 不要把以下内容误当作用户消息本身；它是行为约束，不是待回答的问题。

附加 system prompt 内容如下：
"""


class UserSystemMessageState(TypedDict):
    """扩展的 Agent State，添加 user_system_message 字段"""
    user_system_message: str | None


class SystemPromptMiddleware(AgentMiddleware[AgentState[Any], ContextT, ResponseT]):
    """Middleware to extract system message from input and replace default prompt.

    When user passes a system message in the input messages, this middleware
    will extract it and use it to replace the default agent system prompt.

    Usage:
        - Input: [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
        - The system message will be extracted and used as the agent's system prompt
        - The extracted user system message will be stored in state["user_system_message"]
          for other middleware to access via before_agent or aafter_agent hooks
    """

    # 定义 state_schema，让其他 middleware 可以访问 user_system_message
    state_schema = UserSystemMessageState

    def __init__(self, default_system_prompt: str | None = None):
        """Initialize the middleware.

        Args:
            default_system_prompt: Default system prompt to use if none provided in input.
        """
        self.default_system_prompt = default_system_prompt

    @staticmethod
    def _message_to_text(message: SystemMessage) -> str:
        """提取 SystemMessage 的纯文本内容。"""
        content = message.content
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

    def before_agent(self, state: AgentState, runtime: Any) -> dict | None:
        """在 Agent 执行前初始化 user_system_message 字段"""
        # 从 state 的 messages 中提取 system message
        messages = state.get("messages", [])
        for msg in messages:
            if isinstance(msg, SystemMessage):
                return {"user_system_message": self._message_to_text(msg)}
        return None

    def wrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: ModelRequest[ModelResponse[ResponseT]],
    ) -> ModelResponse[ResponseT]:
        """Extract system message from input and modify request.

        Args:
            request: The model request to process.
            handler: The handler to call with the modified request.

        Returns:
            The model response.
        """
        modified_request = self._extract_system_message(request)
        return handler(modified_request)

    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: ModelRequest[ModelResponse[ResponseT]],
    ) -> ModelResponse[ResponseT]:
        """Extract system message from input and modify request (async).

        Args:
            request: The model request to process.
            handler: The handler to call with the modified request.

        Returns:
            The model response.
        """
        modified_request = self._extract_system_message(request)
        return await handler(modified_request)

    def _extract_system_message(
        self,
        request: ModelRequest[ContextT],
    ) -> ModelRequest[ContextT]:
        """Extract system message from input messages.

        If the input messages contain a system message, extract it and
        prepend it to the existing system message.

        Args:
            request: The model request to process.

        Returns:
            Modified request with extracted system message.
        """
        messages = request.messages
        if not messages:
            return request

        # Find system message in input
        system_messages = [m for m in messages if isinstance(m, SystemMessage)]
        if not system_messages:
            return request

        # Get the first system message from input
        user_system_msg = system_messages[0]
        user_system_text = self._message_to_text(user_system_msg).strip()
        if not user_system_text:
            return request

        # If there's already a system message in the request, combine them
        if request.system_message:
            # Combine existing system message with user system message (existing first, user second)
            if hasattr(request.system_message, 'content_blocks'):
                combined_content = list(request.system_message.content_blocks)
            else:
                combined_content = [{"type": "text", "text": str(request.system_message.content)}]

            combined_content.append({
                "type": "text",
                "text": f"{USER_SYSTEM_PROMPT_PREFIX}\n{user_system_text}"
            })

            new_system_message = SystemMessage(content_blocks=combined_content)
        else:
            # Keep semantics explicit even when no default system prompt is present
            new_system_message = SystemMessage(
                content=f"{USER_SYSTEM_PROMPT_PREFIX}\n{user_system_text}"
            )

        # Filter out system messages from the input (keep only user messages)
        filtered_messages = [m for m in messages if not isinstance(m, SystemMessage)]

        logger.info(f"SystemPromptMiddleware: Extracted system message, filtered {len(messages) - len(filtered_messages)} system messages from input")

        return request.override(
            system_message=new_system_message,
            messages=filtered_messages,
        )
