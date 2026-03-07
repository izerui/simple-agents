"""自定义 LangChain SummarizationMiddleware，支持动态 max_input_tokens。"""
import os
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from langchain.agents.middleware.summarization import SummarizationMiddleware as LCSummarizationMiddleware
from langchain_core.messages import AnyMessage

console = Console()


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
        "minimax": 196608,
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
        from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

        max_input_tokens = self._get_profile_limits()

        # 计算百分比
        percentage = total_tokens / max_input_tokens * 100
        to_summarize = int(max_input_tokens * 0.6) - total_tokens  # 距摘要触发

        # 根据百分比选择颜色
        if percentage < 40:
            color = "green"
        elif percentage < 60:
            color = "yellow"
        else:
            color = "red"

        # 从 get_runtime_config() 获取 model_name 和 thread_id
        model_name, _, thread_id = self._get_runtime_config()

        # 使用动画进度条
        progress = Progress(
            SpinnerColumn(style=color, speed=0.5),
            TextColumn("[bold]{task.description}[/]"),
            BarColumn(bar_width=40),
            TextColumn("[bold]{task.percentage:>3.0f}%[/]"),
            console=console,
            transient=True,
        )

        # 创建进度条任务
        with progress:
            progress.add_task(
                f"[{color}]Token[/] [white]使用进度[/]",
                total=100,
                completed=min(percentage, 100),
            )

        # 直接打印输出，无边框
        console.print("-" * 80)
        console.print(f"  Thread: {thread_id or 'Unknown'}")
        console.print(f"  Model: {model_name or 'Unknown'}")

        # 进度条
        bar_filled = int(percentage / 5)
        bar_str = f"[{color}]{'█' * bar_filled}[/{color}][dim]{'░' * (20 - bar_filled)}[/]"
        if to_summarize > 0:
            console.print(f"  Tokens: {bar_str} {percentage:.1f}% [blue]已用/限额: {total_tokens:,}[/][dim]/[/][red]{max_input_tokens:,}[/]  [dim]距摘要 {to_summarize:,}[/]")
        else:
            console.print(f"  Tokens: {bar_str} {percentage:.1f}% [blue]已用/限额: {total_tokens:,}[/][dim]/[/][red]{max_input_tokens:,}[/]  [bold red]距摘要已触发![/]")
        console.print("-" * 80)

        return super()._should_summarize(messages, total_tokens)
