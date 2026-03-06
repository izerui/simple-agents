"""自定义 LangChain SummarizationMiddleware，支持动态 max_input_tokens。"""
import logging
import os
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

        优先级：客户端传递 > 映射表 > 环境变量默认 > model.profile
        """
        # 获取配置信息，max_input_tokens 已经在方法内完成优先级判断
        _, max_input_tokens, _ = self._get_runtime_config()

        # 如果仍然获取不到，fallback 到父类
        if max_input_tokens is None:
            return super()._get_profile_limits()

        return max_input_tokens

    def _get_runtime_config(self) -> tuple[str | None, int | None, str | None]:
        """从 get_config() 获取运行时配置。

        max_input_tokens 优先级：客户端传递 > 映射表 > 环境变量默认

        Returns:
            tuple: (model_name, max_input_tokens, thread_id)
        """
        cfg = self._get_langgraph_config()
        if not cfg:
            # 无法获取配置，使用环境变量默认值
            return None, int(os.getenv('MODEL_MAX_INPUT_TOKENS', '80000')), None

        configurable = cfg.get("configurable", {})

        # model_name: configurable -> 环境变量
        model_name = configurable.get("model") or os.getenv('MODEL_MODEL_ID')

        # max_input_tokens 优先级判断
        max_input_tokens = configurable.get("max_input_tokens")
        if max_input_tokens is None and model_name:
            # 尝试从映射表获取
            max_input_tokens = self._get_max_input_tokens_from_model(model_name)
        if max_input_tokens is None:
            # 使用环境变量默认
            max_input_tokens = int(os.getenv('MODEL_MAX_INPUT_TOKENS', '80000'))

        # thread_id: configurable
        thread_id = configurable.get("thread_id")

        return model_name, max_input_tokens, thread_id

    def _get_max_input_tokens_from_model(self, model_name: str) -> int | None:
        """根据模型名称从映射表获取 max_input_tokens。

        Args:
            model_name: 模型名称

        Returns:
            max_input_tokens 或 None
        """
        if not model_name:
            return None

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

        # 从 get_runtime_config() 获取 model_name 和 thread_id
        model_name, _, thread_id = self._get_runtime_config()

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

