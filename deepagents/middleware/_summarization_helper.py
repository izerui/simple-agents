"""自定义 LangChain SummarizationMiddleware，支持动态 max_input_tokens。"""
import logging
import os
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware.summarization import SummarizationMiddleware as LCSummarizationMiddleware
from langchain_core.messages import AnyMessage

if TYPE_CHECKING:
    from langchain.agents.middleware.types import ModelRequest

# 用于存储当前请求的 max_input_tokens
_current_max_input_tokens: ContextVar[int | None] = ContextVar("current_max_input_tokens", default=None)
# 用于存储当前模型名称
_current_model_name: ContextVar[str | None] = ContextVar("current_model_name", default=None)
# 用于存储当前 thread_id
_current_thread_id: ContextVar[str | None] = ContextVar("current_thread_id", default=None)


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
        if max_input_tokens is not None:
            return max_input_tokens

        # 2. 从 model.profile 获取默认值
        return super()._get_profile_limits()

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

        # 设置当前模型名称
        if request.model:
            model_name = getattr(request.model, 'model', None)
            if model_name:
                _current_model_name.set(model_name)

        # 设置当前 thread_id
        thread_id = runtime_config.get('configurable', {}).get('thread_id')
        _current_thread_id.set(thread_id)

    def _should_summarize(self, messages: list[AnyMessage], total_tokens: int) -> bool:
        max_input_tokens = self._get_profile_limits()

        # 绿色表示安全，黄色警告，红色危险
        percentage = total_tokens / max_input_tokens * 100

        if percentage < 40:
            # 主状态颜色
            status_color = "\033[92m"  # 绿色
            icon = "🟢"
            # 数值颜色（浅绿）
            value_color = "\033[32m"
            # 进度条颜色（亮绿）
            bar_color = "\033[92m"
            # 百分比颜色（深绿）
            percent_color = "\033[32m"
        elif percentage < 60:
            # 主状态颜色
            status_color = "\033[93m"  # 黄色
            icon = "🟡"
            # 数值颜色（浅黄）
            value_color = "\033[33m"
            # 进度条颜色（亮黄）
            bar_color = "\033[93m"
            # 百分比颜色（深黄）
            percent_color = "\033[33m"
        else:
            # 主状态颜色
            status_color = "\033[91m"  # 红色
            icon = "🔴"
            # 数值颜色（浅红）
            value_color = "\033[31m"
            # 进度条颜色（亮红）
            bar_color = "\033[91m"
            # 百分比颜色（深红）
            percent_color = "\033[31m"

        reset = "\033[0m"
        bold = "\033[1m"

        # 获取当前模型名称
        model_name = _current_model_name.get()
        model_display = f"{value_color}{bold}{model_name}{reset}" if model_name else "Unknown"

        # 获取当前 thread_id
        thread_id = _current_thread_id.get()
        thread_display = f"{value_color}{bold}{thread_id}{reset}" if thread_id else "Unknown"

        # 创建彩色进度条
        bar_length = 12
        filled_length = min(int(bar_length * percentage / 100), bar_length)
        colored_bar = f"{bar_color}{'█' * filled_length}{reset}{'░' * (bar_length - filled_length)}"

        logging.info(
            f"{status_color}{bold}📱{icon}{reset} "
            f"Thread: {thread_display} | "
            f"Model: {model_display} | "
            f"Tokens: {value_color}{bold}{total_tokens:,}{reset}/{value_color}{bold}{max_input_tokens:,}{reset} "
            f"📊[{colored_bar}] "
            f"📈{percent_color}{bold}({percentage:.1f}%){reset}"
        )

        return super()._should_summarize(messages, total_tokens)

