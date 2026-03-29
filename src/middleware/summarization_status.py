"""摘要压缩状态打印中间件。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware, ContextT, ModelRequest, ModelResponse, ResponseT
from langchain_core.messages import AnyMessage
from langchain_core.messages.utils import count_tokens_approximately
from langgraph.config import get_config
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

console = Console()


class SummarizationStatusMiddleware(AgentMiddleware):
    """打印当前上下文占用情况，便于观察自动压缩触发时机。"""

    def wrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], ModelResponse[ResponseT]],
    ) -> ModelResponse[ResponseT]:
        self._print_status(request)
        return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
    ) -> ModelResponse[ResponseT]:
        self._print_status(request)
        return await handler(request)

    def _print_status(self, request: ModelRequest[ContextT]) -> None:
        max_input_tokens = self._get_profile_limit(request)
        if max_input_tokens is None or max_input_tokens <= 0:
            return

        counted_messages = self._build_counted_messages(request)
        total_tokens = count_tokens_approximately(counted_messages)
        percentage = total_tokens / max_input_tokens * 100
        to_summarize = int(max_input_tokens * 0.85) - total_tokens

        if percentage < 40:
            color = "green"
        elif percentage < 60:
            color = "yellow"
        else:
            color = "red"

        runtime_config = self._get_runtime_config()
        model_name = runtime_config["model_name"]
        thread_id = runtime_config["thread_id"]
        tags = runtime_config["tags"]
        user_id = runtime_config["user_id"]
        name = runtime_config["name"]

        progress = Progress(
            SpinnerColumn(style=color, speed=0.5),
            TextColumn("[bold]{task.description}[/]"),
            BarColumn(bar_width=40),
            TextColumn("[bold]{task.percentage:>3.0f}%[/]"),
            console=console,
            transient=True,
        )

        with progress:
            progress.add_task(
                f"[{color}]Token[/] [white]使用进度[/]",
                total=100,
                completed=min(percentage, 100),
            )

        console.print("-" * 80)
        console.print(f"  Thread: {thread_id or 'Unknown'}")
        console.print(f"  Model: {model_name or 'Unknown'}")
        console.print(f"  User: {user_id or 'Unknown'}")
        console.print(f"  Name: {name or 'Unknown'}")
        console.print(f"  Tags: {', '.join(tags) if tags else 'None'}")

        bar_filled = int(min(max(percentage, 0), 100) / 5)
        bar_str = f"[{color}]{'█' * bar_filled}[/{color}][dim]{'░' * (20 - bar_filled)}[/]"
        if to_summarize > 0:
            console.print(
                f"  Tokens: {bar_str} {percentage:.1f}% "
                f"[blue]已用/限额: {total_tokens:,}[/][dim]/[/][red]{max_input_tokens:,}[/]  "
                f"[dim]距摘要 {to_summarize:,}[/]"
            )
        else:
            console.print(
                f"  Tokens: {bar_str} {percentage:.1f}% "
                f"[blue]已用/限额: {total_tokens:,}[/][dim]/[/][red]{max_input_tokens:,}[/]  "
                f"[bold red]摘要压缩即将触发![/]"
            )
        console.print("-" * 80)

    def _build_counted_messages(self, request: ModelRequest[ContextT]) -> list[AnyMessage]:
        counted_messages = list(request.messages)
        if request.system_message is not None:
            counted_messages = [request.system_message, *counted_messages]
        return counted_messages

    def _get_profile_limit(self, request: ModelRequest[ContextT]) -> int | None:
        profile = getattr(request.model, "profile", None)
        if isinstance(profile, dict):
            value = profile.get("max_input_tokens")
            if isinstance(value, int) and value > 0:
                return value
        return None

    def _get_runtime_config(self) -> dict[str, Any]:
        try:
            cfg = get_config()
        except RuntimeError:
            cfg = None

        if not isinstance(cfg, dict):
            return {
                "model_name": None,
                "thread_id": None,
                "tags": [],
                "user_id": None,
                "name": None,
            }

        configurable = cfg.get("configurable", {})
        metadata = cfg.get("metadata", {})
        config = cfg.get("config", {})

        return {
            "model_name": configurable.get("model"),
            "thread_id": configurable.get("thread_id"),
            "tags": config.get("tags", []),
            "user_id": metadata.get("user_id"),
            "name": metadata.get("name"),
        }
