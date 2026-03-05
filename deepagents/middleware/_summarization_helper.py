"""自定义 LangChain SummarizationMiddleware，支持动态 max_input_tokens。"""
import logging
import os
from typing import Any

from langchain.agents.middleware.summarization import SummarizationMiddleware as LCSummarizationMiddleware
from langchain_core.messages import AnyMessage


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

    @staticmethod
    def _get_langgraph_config() -> dict | None:
        """从 langgraph.config.get_config() 获取配置信息。"""
        try:
            from langgraph.config import get_config

            cfg = get_config()
            if isinstance(cfg, dict):
                return cfg
        except Exception:
            pass
        return None

    def _get_profile_limits(self) -> int | None:
        """Retrieve max input token limit with dynamic support.

        优先级：客户端传递 > 映射表 > model.profile
        """
        # 从 get_config() 获取配置信息
        cfg = self._get_langgraph_config()
        if cfg:
            configurable = cfg.get("configurable", {})
            model_name = configurable.get("model")
            max_input_tokens = configurable.get("max_input_tokens")
            result = self._get_max_input_tokens(
                model=model_name,
                max_input_tokens=max_input_tokens
            )
            if result is not None:
                return result

        # 2. 从 model.profile 获取默认值
        return super()._get_profile_limits()

    def _get_max_input_tokens(self, model: Any = None, max_input_tokens: int | None = None) -> int | None:
        """获取 max_input_tokens，优先级：客户端传递 > 映射表 > 默认 profile

        Args:
            model: 模型名称
            max_input_tokens: 客户端传递的 max_input_tokens
        """
        # 1. 直接使用客户端传递的 max_input_tokens
        if max_input_tokens is not None:
            return max_input_tokens

        # 2. 尝试从映射表获取
        if model:
            # 支持 model 是字符串或对象
            model_name = model if isinstance(model, str) else getattr(model, 'model', None)
            if not model_name:
                model_name = os.getenv('MODEL_MODEL_ID', '')
            if model_name:
                model_lower = model_name.lower()
                sorted_keys = sorted(self.MODEL_MAX_INPUT_TOKENS.keys(), key=len, reverse=True)
                for key in sorted_keys:
                    if model_lower.startswith(key):
                        return self.MODEL_MAX_INPUT_TOKENS[key]

        return None

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

        # 从 get_config() 获取 model_name 和 thread_id
        cfg = self._get_langgraph_config()
        if cfg:
            configurable = cfg.get("configurable", {})
            model_name = configurable.get("model")
            thread_id = configurable.get("thread_id")
        else:
            model_name = None
            thread_id = None

        model_display = f"{value_color}{bold}{model_name}{reset}" if model_name else "Unknown"
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

