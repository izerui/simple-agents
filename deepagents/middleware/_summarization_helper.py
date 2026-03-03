"""自定义 LangChain SummarizationMiddleware，支持动态 max_input_tokens。"""
import logging
import os
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware.summarization import SummarizationMiddleware as LCSummarizationMiddleware

if TYPE_CHECKING:
    from langchain.agents.middleware.types import ModelRequest

# 用于存储当前请求的 max_input_tokens
_current_max_input_tokens: ContextVar[int | None] = ContextVar("current_max_input_tokens", default=None)


class DeepAgentsLCSummarizationMiddleware(LCSummarizationMiddleware):
    """自定义 LCSummarizationMiddleware，支持动态 max_input_tokens"""

    # 模型最大输入 token 映射表
    MODEL_MAX_INPUT_TOKENS = {
        "deepseek-v3": 131072,
        "deepseek-v3.2": 98304,
        "deepseek-v3.1": 98304,
        "deepseek-r1": 98304,
        "qwen3-max": 258048,
        "qwen3.5-plus": 983616,
        "kimi-k2.5": 262144,
        "glm-5": 202752,
        "glm-4.7": 169984,
        "MiniMax-M2.5": 196608,
    }

    def _get_profile_limits(self) -> int | None:
        """Retrieve max input token limit with dynamic support.

        优先级：客户端传递 > 映射表 > model.profile
        """
        # 1. 优先从 contextvar 获取动态 max_input_tokens
        max_input_tokens = _current_max_input_tokens.get()
        logging.info(f"[_get_profile_limits] contextvar max_input_tokens: {max_input_tokens}")
        if max_input_tokens is not None:
            return max_input_tokens

        # 2. 从 model.profile 获取默认值
        profile_max = super()._get_profile_limits()
        logging.info(f"[_get_profile_limits] profile max_input_tokens: {profile_max}")
        return profile_max

    def _get_max_input_tokens(self, model: Any = None, runtime_config: dict | None = None) -> int | None:
        """获取 max_input_tokens，优先级：客户端传递 > 映射表 > 默认 profile

        Args:
            model: 模型对象，可通过 model.model 获取模型名称
            runtime_config: 运行时配置，可通过 runtime.config 获取
        """
        # 1. 尝试从客户端传递的 runtime config 获取
        if runtime_config:
            logging.info(f"runtime config : {runtime_config}")
            max_input_tokens = runtime_config.get('max_input_tokens')
            if max_input_tokens is not None:
                return max_input_tokens

        # 2. 尝试从映射表获取
        if model:
            model_name = getattr(model, 'model', None) or os.getenv('MODEL_MODEL_ID', '')
            if model_name:
                model_lower = model_name.lower()
                sorted_keys = sorted(self.MODEL_MAX_INPUT_TOKENS.keys(), key=len, reverse=True)
                for key in sorted_keys:
                    if model_lower.startswith(key):
                        return self.MODEL_MAX_INPUT_TOKENS[key]

        return None

    def _set_max_input_tokens_from_request(self, request: "ModelRequest") -> None:
        """从 request 中提取 max_input_tokens 并设置到 contextvar。

        Args:
            request: Model request to get runtime config for dynamic max_input_tokens.
        """
        runtime_config = getattr(request.runtime, 'context', {})
        max_input_tokens = self._get_max_input_tokens(
            model=request.model,
            runtime_config=runtime_config
        )
        _current_max_input_tokens.set(max_input_tokens)
