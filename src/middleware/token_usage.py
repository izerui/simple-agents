"""Token 用量统计中间件。

在每次模型调用后提取本次 token usage，并累计到 state 中。
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, TypedDict

from langchain.agents.middleware import AgentMiddleware, AgentState
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)


class TokenUsageRecord(TypedDict):
    """单次模型调用的 token 统计。"""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class TokenUsageAggregate(TypedDict):
    """累计 token 统计。"""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    llm_call_count: int
    records: list[TokenUsageRecord]


def _to_records(value: Any) -> list[TokenUsageRecord]:
    if isinstance(value, list):
        return [record for record in value if isinstance(record, dict)]
    return []


def _merge_token_usage(left: Any, right: Any) -> TokenUsageAggregate:
    """合并两段 token 统计，供 state reducer 使用。"""
    left_dict = left if isinstance(left, dict) else {}
    right_dict = right if isinstance(right, dict) else {}

    return {
        "prompt_tokens": _safe_int(left_dict.get("prompt_tokens")) + _safe_int(right_dict.get("prompt_tokens")),
        "completion_tokens": _safe_int(left_dict.get("completion_tokens")) + _safe_int(
            right_dict.get("completion_tokens")
        ),
        "total_tokens": _safe_int(left_dict.get("total_tokens")) + _safe_int(right_dict.get("total_tokens")),
        "llm_call_count": _safe_int(left_dict.get("llm_call_count")) + _safe_int(right_dict.get("llm_call_count")),
        "records": _to_records(left_dict.get("records")) + _to_records(right_dict.get("records")),
    }


class TokenUsageState(TypedDict):
    """扩展 Agent State，支持 token 累加统计。"""

    token_usage: Annotated[TokenUsageAggregate, _merge_token_usage]


def _safe_int(value: Any) -> int:
    """将任意值转为非负整数。"""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def _pick_usage_counts(raw_usage: dict[str, Any]) -> tuple[int, int, int]:
    """从单个 usage 字典中提取标准化 token 计数。"""
    prompt_tokens = _safe_int(raw_usage.get("input_tokens"))
    if not prompt_tokens:
        prompt_tokens = _safe_int(raw_usage.get("prompt_tokens"))

    completion_tokens = _safe_int(raw_usage.get("output_tokens"))
    if not completion_tokens:
        completion_tokens = _safe_int(raw_usage.get("completion_tokens"))

    total_tokens = _safe_int(raw_usage.get("total_tokens"))
    if not total_tokens and (prompt_tokens or completion_tokens):
        total_tokens = prompt_tokens + completion_tokens

    return prompt_tokens, completion_tokens, total_tokens


def _extract_usage_counts(message: Any) -> tuple[int, int, int]:
    """从消息对象提取 token usage。

    兼容多种返回结构：
    - message.usage_metadata
    - message.response_metadata["token_usage"]
    - message.response_metadata["usage"]
    - message.response_metadata["usage_metadata"]
    - message.response_metadata（根级直接带 token 字段）
    """
    candidates: list[dict[str, Any]] = []

    usage_metadata = getattr(message, "usage_metadata", None)
    if isinstance(usage_metadata, dict):
        candidates.append(usage_metadata)

    response_metadata = getattr(message, "response_metadata", None)
    if isinstance(response_metadata, dict):
        token_usage = response_metadata.get("token_usage")
        usage = response_metadata.get("usage")
        usage_meta = response_metadata.get("usage_metadata")
        if isinstance(token_usage, dict):
            candidates.append(token_usage)
        if isinstance(usage, dict):
            candidates.append(usage)
        if isinstance(usage_meta, dict):
            candidates.append(usage_meta)
        candidates.append(response_metadata)

    for raw_usage in candidates:
        prompt_tokens, completion_tokens, total_tokens = _pick_usage_counts(raw_usage)
        if prompt_tokens or completion_tokens or total_tokens:
            return prompt_tokens, completion_tokens, total_tokens

    return 0, 0, 0


class TokenUsageMiddleware(AgentMiddleware):
    """在每次模型调用后累计 token 用量到 state。"""

    state_schema = TokenUsageState

    def after_model(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:  # noqa: ARG002
        messages = state.get("messages", [])
        if not messages:
            return None

        last_message = messages[-1]
        prompt_tokens, completion_tokens, total_tokens = _extract_usage_counts(last_message)
        if not (prompt_tokens or completion_tokens or total_tokens):
            return None

        record: TokenUsageRecord = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }

        logger.debug(
            "TokenUsageMiddleware: prompt=%s, completion=%s, total=%s",
            prompt_tokens,
            completion_tokens,
            total_tokens,
        )
        return {
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "llm_call_count": 1,
                "records": [record],
            }
        }
