"""Dynamic BaseChatModel proxy compatible with deepagents.

This proxy keeps deepagents' `BaseChatModel` contract intact while allowing the
actual provider/model/base_url/api_key to be selected per request from
`config.configurable`.
"""

from __future__ import annotations

import os
from hashlib import sha256
from threading import Lock
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.config import get_config
from pydantic import Field, PrivateAttr

from src.utils.model_config import _is_truthy, _thinking_control_kwargs


class DynamicChatModel(BaseChatModel):
    """面向 provider 模型的轻量 `BaseChatModel` 路由层。

    这个类本身不实现任何 provider 行为，只负责：
    1. 从 `config.configurable` 解析本次请求的实际模型配置
    2. 构造并缓存真实的 provider 模型（`ChatOpenAI`、`ChatAnthropic` 等）
    3. 暴露动态 `profile`，让自动压缩逻辑能跟随当前模型调整上下文上限

    说明：
        理想情况下，这种 router 只需要实现
        `_generate/_agenerate/_stream/_astream`，把 `invoke/ainvoke/stream/astream`
        交给 `BaseChatModel` 默认实现处理。

        但这个项目还需要支持 `bind_tools()` 和 `with_structured_output()`。
        这些 provider 原生方法返回的结果不一定还是 `BaseChatModel`，很多时候会
        是普通 `Runnable`。因此这里保留 `invoke/ainvoke/stream/astream` 的直接
        转发，确保真正执行的仍然是底层 provider 的原生实现，而不是被 router
        自己截断或改写。
    """

    MODEL_MAX_INPUT_TOKENS: dict[str, int] = {
        "deepseek-v3": 131072,
        "deepseek-v3.2": 98304,
        "deepseek-v3.1": 98304,
        "deepseek-r1": 98304,
        "qwen3-max": 80000,
        "qwen3.5-plus": 983616,
        "kimi-k2.5": 262144,
        "glm-5": 202752,
        "glm-4.7": 169984,
        "minimax": 196608,
    }

    default_kwargs: dict[str, Any] = Field(default_factory=dict)
    queued_declarative_operations: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = Field(
        default_factory=list
    )
    _model_cache: dict[tuple[Any, ...], Runnable] = PrivateAttr(default_factory=dict)
    _cache_lock: Lock = PrivateAttr(default_factory=Lock)

    @property
    def _llm_type(self) -> str:
        return "dynamic_chat_model"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {
            "default_model": self.default_kwargs.get("model"),
            "default_provider": self.default_kwargs.get("model_provider"),
        }

    def __getattribute__(self, name: str) -> Any:
        if name == "profile":
            return object.__getattribute__(self, "_get_runtime_profile")()
        return super().__getattribute__(name)

    def bind_tools(
        self,
        tools: list[dict[str, Any] | type | Any] | tuple[dict[str, Any] | type | Any, ...],
        *,
        tool_choice: Any = None,
        **kwargs: Any,
    ) -> Runnable:
        return self._queue_operation(
            "bind_tools",
            (list(tools),),
            {"tool_choice": tool_choice, **kwargs},
        )

    def with_structured_output(
        self,
        schema: dict[str, Any] | type,
        *,
        include_raw: bool = False,
        **kwargs: Any,
    ) -> Runnable:
        return self._queue_operation(
            "with_structured_output",
            (schema,),
            {"include_raw": include_raw, **kwargs},
        )

    def _queue_operation(
        self,
        name: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> "DynamicChatModel":
        operations = [*self.queued_declarative_operations, (name, args, kwargs)]
        return self.model_copy(update={"queued_declarative_operations": operations})

    def _get_configurable(self, config: RunnableConfig | None = None) -> dict[str, Any]:
        if config and isinstance(config, dict):
            configurable = config.get("configurable")
            if isinstance(configurable, dict):
                return configurable

        try:
            runtime_config = get_config()
        except RuntimeError:
            return {}

        if isinstance(runtime_config, dict):
            configurable = runtime_config.get("configurable")
            if isinstance(configurable, dict):
                return configurable
        return {}

    def _get_effective_kwargs(self, config: RunnableConfig | None = None) -> dict[str, Any]:
        configurable = self._get_configurable(config)
        kwargs = dict(self.default_kwargs)

        for key in ("model", "model_provider", "base_url", "api_key"):
            value = configurable.get(key)
            if value is not None:
                kwargs[key] = value

        # Recompute provider-specific thinking toggles against the effective model.
        kwargs.pop("extra_body", None)
        kwargs.pop("thinking", None)
        provider = kwargs.get("model_provider")
        model = kwargs.get("model")
        if provider == "openai" and not _is_truthy(os.getenv("L_MODEL_ENABLE_THINKING")):
            kwargs.update(_thinking_control_kwargs(model))

        return kwargs

    def _build_runtime_model(self, config: RunnableConfig | None = None) -> Runnable:
        effective_kwargs = self._get_effective_kwargs(config)
        cache_key = self._build_cache_key(effective_kwargs)
        cached = self._model_cache.get(cache_key)
        if cached is not None:
            return cached

        # 双重检查 + 互斥锁，避免并发首建同一模型配置时重复初始化。
        with self._cache_lock:
            cached = self._model_cache.get(cache_key)
            if cached is not None:
                return cached

            model = init_chat_model(**effective_kwargs)
            for name, args, kwargs in self.queued_declarative_operations:
                model = getattr(model, name)(*args, **kwargs)
            self._model_cache[cache_key] = model
            return model

    def _build_cache_key(self, effective_kwargs: dict[str, Any]) -> tuple[Any, ...]:
        normalized_kwargs = tuple(
            sorted((key, self._freeze_for_cache(value)) for key, value in effective_kwargs.items())
        )
        normalized_ops = tuple(
            (
                name,
                self._freeze_for_cache(args),
                self._freeze_for_cache(kwargs),
            )
            for name, args, kwargs in self.queued_declarative_operations
        )
        return normalized_kwargs + (("__ops__", normalized_ops),)

    def _freeze_for_cache(self, value: Any) -> Any:
        if isinstance(value, dict):
            return tuple(sorted((k, self._freeze_for_cache(v)) for k, v in value.items()))
        if isinstance(value, (list, tuple)):
            return tuple(self._freeze_for_cache(v) for v in value)
        if isinstance(value, set):
            return tuple(sorted(self._freeze_for_cache(v) for v in value))
        if isinstance(value, str):
            if len(value) > 24 and ("sk-" in value or "api" in value.lower() or "key" in value.lower()):
                return ("sha256", sha256(value.encode("utf-8")).hexdigest())
            return value
        try:
            hash(value)
            return value
        except TypeError:
            return repr(value)

    def invoke(
        self,
        input: Any,
        config: RunnableConfig | None = None,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> AIMessage:
        # 这里必须直接转发给解析后的 runnable，才能兼容 bind_tools /
        # with_structured_output 返回普通 Runnable 的情况。
        model = self._build_runtime_model(config)
        return model.invoke(input, config=config, stop=stop, **kwargs)

    async def ainvoke(
        self,
        input: Any,
        config: RunnableConfig | None = None,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> AIMessage:
        model = self._build_runtime_model(config)
        return await model.ainvoke(input, config=config, stop=stop, **kwargs)

    def stream(
        self,
        input: Any,
        config: RunnableConfig | None = None,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ):
        model = self._build_runtime_model(config)
        yield from model.stream(input, config=config, stop=stop, **kwargs)

    async def astream(
        self,
        input: Any,
        config: RunnableConfig | None = None,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ):
        model = self._build_runtime_model(config)
        async for chunk in model.astream(input, config=config, stop=stop, **kwargs):
            yield chunk

    def _get_runtime_profile(self) -> dict[str, int]:
        return self._get_runtime_profile_for_config({"configurable": self._get_configurable()})

    def _get_runtime_profile_for_config(self, config: RunnableConfig | dict[str, Any] | None) -> dict[str, int]:
        configurable = self._get_configurable(config if isinstance(config, dict) else config)

        max_input_tokens = configurable.get("max_input_tokens")
        if isinstance(max_input_tokens, int):
            return {"max_input_tokens": max_input_tokens}

        model_name = configurable.get("model") or self.default_kwargs.get("model")
        if isinstance(model_name, str):
            mapped = self._get_max_input_tokens_from_model(model_name)
            if mapped is not None:
                return {"max_input_tokens": mapped}

        env_limit = os.getenv("L_MODEL_MAX_INPUT_TOKENS", "80000")
        return {"max_input_tokens": int(env_limit)}

    def _get_max_input_tokens_from_model(self, model_name: str) -> int | None:
        model_lower = model_name.lower()
        for key in sorted(self.MODEL_MAX_INPUT_TOKENS, key=len, reverse=True):
            if model_lower.startswith(key):
                return self.MODEL_MAX_INPUT_TOKENS[key]
        return None

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        model = self._build_runtime_model()
        return model._generate(messages, stop=stop, run_manager=run_manager, **kwargs)  # type: ignore[attr-defined]

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        model = self._build_runtime_model()
        return await model._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)  # type: ignore[attr-defined]

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ):
        model = self._build_runtime_model()
        for chunk in model._stream(messages, stop=stop, run_manager=run_manager, **kwargs):  # type: ignore[attr-defined]
            if isinstance(chunk, ChatGenerationChunk):
                yield chunk
            else:
                yield ChatGenerationChunk(message=chunk)

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ):
        model = self._build_runtime_model()
        async for chunk in model._astream(messages, stop=stop, run_manager=run_manager, **kwargs):  # type: ignore[attr-defined]
            if isinstance(chunk, ChatGenerationChunk):
                yield chunk
            else:
                yield ChatGenerationChunk(message=chunk)
