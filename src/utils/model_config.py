"""Helpers for chat model initialization."""

from __future__ import annotations

import os
from typing import Any


def _is_truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def get_model_init_kwargs(*, streaming: bool, temperature: float = 0.0) -> dict[str, Any]:
    """Build common init kwargs for chat models.

    DashScope's OpenAI-compatible chat/completions API can require
    `reasoning_content` to be echoed back when provider-side thinking is enabled.
    `langchain-openai` does not preserve that non-standard field, so we disable
    thinking by default on this compatibility path to keep multi-turn tool use
    working. Set `L_MODEL_ENABLE_THINKING=true` to opt back in explicitly.
    """
    kwargs: dict[str, Any] = {
        "model": os.getenv("L_MODEL_MODEL_ID"),
        "model_provider": os.getenv("L_MODEL_PROVIDER"),
        "base_url": os.getenv("L_MODEL_BASE_URL"),
        "api_key": os.getenv("L_MODEL_API_KEY"),
        "temperature": temperature,
        "streaming": streaming,
    }

    provider = os.getenv("L_MODEL_PROVIDER")
    if provider == "openai" and not _is_truthy(os.getenv("L_MODEL_ENABLE_THINKING")):
        kwargs["extra_body"] = {"enable_thinking": False}

    return kwargs
