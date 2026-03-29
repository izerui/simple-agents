from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import time
from unittest.mock import patch

from src.utils.dynamic_chat_model import DynamicChatModel
from pydantic import BaseModel


def test_profile_uses_default_model_mapping():
    model = DynamicChatModel(
        default_kwargs={
            "model": "qwen3-max",
            "model_provider": "openai",
            "streaming": True,
        }
    )

    assert model.profile == {"max_input_tokens": 80000}


def test_cache_key_changes_with_runtime_model():
    model = DynamicChatModel(
        default_kwargs={
            "model": "qwen3-max",
            "model_provider": "openai",
            "streaming": True,
        }
    )

    key1 = model._build_cache_key(model._get_effective_kwargs({"configurable": {"model": "qwen3-max"}}))
    key2 = model._build_cache_key(model._get_effective_kwargs({"configurable": {"model": "deepseek-v3.2"}}))

    assert key1 != key2


def test_bind_tools_keeps_tools_as_single_positional_argument():
    model = DynamicChatModel(
        default_kwargs={
            "model": "qwen3-max",
            "model_provider": "openai",
            "streaming": True,
        }
    )

    bound = model.bind_tools([{"name": "tool_a"}, {"name": "tool_b"}])

    name, args, kwargs = bound.queued_declarative_operations[0]
    assert name == "bind_tools"
    assert len(args) == 1
    assert isinstance(args[0], list)
    assert [tool["name"] for tool in args[0]] == ["tool_a", "tool_b"]
    assert "tool_choice" in kwargs


def test_bind_tools_preserves_non_string_tool_choice():
    model = DynamicChatModel(
        default_kwargs={
            "model": "qwen3-max",
            "model_provider": "openai",
            "streaming": True,
        }
    )

    tool_choice = {"type": "function", "function": {"name": "tool_a"}}
    bound = model.bind_tools([{"name": "tool_a"}], tool_choice=tool_choice)

    _, _, kwargs = bound.queued_declarative_operations[0]
    assert kwargs["tool_choice"] == tool_choice


def test_with_structured_output_keeps_schema_as_single_positional_argument():
    class OutputSchema(BaseModel):
        value: int

    model = DynamicChatModel(
        default_kwargs={
            "model": "qwen3-max",
            "model_provider": "openai",
            "streaming": True,
        }
    )

    wrapped = model.with_structured_output(OutputSchema, include_raw=True, method="json_schema")

    name, args, kwargs = wrapped.queued_declarative_operations[0]
    assert name == "with_structured_output"
    assert len(args) == 1
    assert args[0] is OutputSchema
    assert kwargs["include_raw"] is True
    assert kwargs["method"] == "json_schema"


def test_runtime_model_cache_is_thread_safe_for_same_config():
    model = DynamicChatModel(
        default_kwargs={
            "model": "qwen3-max",
            "model_provider": "openai",
            "streaming": True,
        }
    )
    barrier = Barrier(4)
    init_calls = 0

    class FakeRunnable:
        def bind_tools(self, *args, **kwargs):
            return self

        def with_structured_output(self, *args, **kwargs):
            return self

    def fake_init_chat_model(**kwargs):
        nonlocal init_calls
        time.sleep(0.05)
        init_calls += 1
        return FakeRunnable()

    config = {"configurable": {"model": "qwen3-max"}}
    with patch("src.utils.dynamic_chat_model.init_chat_model", side_effect=fake_init_chat_model):
        with ThreadPoolExecutor(max_workers=4) as executor:
            def worker(_):
                barrier.wait()
                return model._build_runtime_model(config)

            results = list(executor.map(worker, range(4)))

    assert init_calls == 1
    assert len({id(result) for result in results}) == 1


def test_runtime_model_cache_keeps_different_configs_isolated():
    model = DynamicChatModel(
        default_kwargs={
            "model": "qwen3-max",
            "model_provider": "openai",
            "streaming": True,
        }
    )
    barrier = Barrier(4)
    init_calls: list[str] = []

    class FakeRunnable:
        def __init__(self, model_name: str):
            self.model_name = model_name

        def bind_tools(self, *args, **kwargs):
            return self

        def with_structured_output(self, *args, **kwargs):
            return self

    def fake_init_chat_model(**kwargs):
        model_name = kwargs["model"]
        time.sleep(0.05)
        init_calls.append(model_name)
        return FakeRunnable(model_name)

    configs = [
        {"configurable": {"model": "qwen3-max"}},
        {"configurable": {"model": "qwen3-max"}},
        {"configurable": {"model": "deepseek-v3.2"}},
        {"configurable": {"model": "deepseek-v3.2"}},
    ]
    with patch("src.utils.dynamic_chat_model.init_chat_model", side_effect=fake_init_chat_model):
        with ThreadPoolExecutor(max_workers=4) as executor:
            def worker(config):
                barrier.wait()
                return model._build_runtime_model(config)

            results = list(executor.map(worker, configs))

    assert sorted(init_calls) == ["deepseek-v3.2", "qwen3-max"]
    assert results[0] is results[1]
    assert results[2] is results[3]
    assert results[0] is not results[2]
