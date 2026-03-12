"""自定义 system prompt 处理中间件。

用于从输入消息中提取 system message，替换默认的 agent prompt。
这样可以支持在 API 请求中传递自定义 system prompt。
"""
import logging
from typing import Any, Sequence

from langchain.agents.middleware.types import AgentMiddleware, AgentState, ContextT, ModelRequest, ModelResponse, ResponseT
from langchain_core.messages import AnyMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)


class SystemPromptMiddleware(AgentMiddleware[AgentState[Any], ContextT, ResponseT]):
    """Middleware to extract system message from input and replace default prompt.

    When user passes a system message in the input messages, this middleware
    will extract it and use it to replace the default agent system prompt.

    Usage:
        - Input: [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
        - The system message will be extracted and used as the agent's system prompt
    """

    def __init__(self, default_system_prompt: str | None = None):
        """Initialize the middleware.

        Args:
            default_system_prompt: Default system prompt to use if none provided in input.
        """
        self.default_system_prompt = default_system_prompt

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

        # If there's already a system message in the request, combine them
        if request.system_message:
            # Combine existing system message with user system message (existing first, user second)
            if hasattr(request.system_message, 'content_blocks'):
                combined_content = list(request.system_message.content_blocks)
            else:
                combined_content = [{"type": "text", "text": str(request.system_message.content)}]

            # Then add user system message after existing
            if hasattr(user_system_msg, 'content_blocks'):
                combined_content.extend(user_system_msg.content_blocks)
            else:
                combined_content.append({"type": "text", "text": str(user_system_msg.content)})

            new_system_message = SystemMessage(content_blocks=combined_content)
        else:
            # Use user system message as the system message
            new_system_message = user_system_msg

        # Filter out system messages from the input (keep only user messages)
        filtered_messages = [m for m in messages if not isinstance(m, SystemMessage)]

        logger.info(f"SystemPromptMiddleware: Extracted system message, filtered {len(messages) - len(filtered_messages)} system messages from input")

        return request.override(
            system_message=new_system_message,
            messages=filtered_messages,
        )
