from src.utils.model_config import get_model_init_kwargs


def test_openai_provider_uses_deepseek_thinking_toggle(monkeypatch):
    monkeypatch.setenv("L_MODEL_PROVIDER", "openai")
    monkeypatch.setenv("L_MODEL_MODEL_ID", "deepseek-v3.2")
    monkeypatch.delenv("L_MODEL_ENABLE_THINKING", raising=False)

    kwargs = get_model_init_kwargs(streaming=True)

    assert kwargs["extra_body"] == {"enable_thinking": False}
    assert "thinking" not in kwargs


def test_openai_provider_uses_kimi_thinking_toggle(monkeypatch):
    monkeypatch.setenv("L_MODEL_PROVIDER", "openai")
    monkeypatch.setenv("L_MODEL_MODEL_ID", "kimi-k2.5")
    monkeypatch.delenv("L_MODEL_ENABLE_THINKING", raising=False)

    kwargs = get_model_init_kwargs(streaming=True)

    assert kwargs["thinking"] == {"type": "disabled"}
    assert "extra_body" not in kwargs


def test_openai_provider_uses_minimax_reasoning_split(monkeypatch):
    monkeypatch.setenv("L_MODEL_PROVIDER", "openai")
    monkeypatch.setenv("L_MODEL_MODEL_ID", "MiniMax-M2.5")
    monkeypatch.delenv("L_MODEL_ENABLE_THINKING", raising=False)

    kwargs = get_model_init_kwargs(streaming=True)

    assert kwargs["extra_body"] == {"reasoning_split": True}
    assert "thinking" not in kwargs


def test_openai_provider_leaves_other_models_unchanged(monkeypatch):
    monkeypatch.setenv("L_MODEL_PROVIDER", "openai")
    monkeypatch.setenv("L_MODEL_MODEL_ID", "qwen3-max")
    monkeypatch.delenv("L_MODEL_ENABLE_THINKING", raising=False)

    kwargs = get_model_init_kwargs(streaming=True)

    assert "extra_body" not in kwargs
    assert "thinking" not in kwargs


def test_openai_provider_allows_explicit_thinking_override(monkeypatch):
    monkeypatch.setenv("L_MODEL_PROVIDER", "openai")
    monkeypatch.setenv("L_MODEL_MODEL_ID", "deepseek-v3.2")
    monkeypatch.setenv("L_MODEL_ENABLE_THINKING", "true")

    kwargs = get_model_init_kwargs(streaming=True)

    assert "extra_body" not in kwargs
    assert "thinking" not in kwargs


def test_non_openai_provider_does_not_inject_thinking_controls(monkeypatch):
    monkeypatch.setenv("L_MODEL_PROVIDER", "anthropic")
    monkeypatch.setenv("L_MODEL_MODEL_ID", "deepseek-v3.2")
    monkeypatch.delenv("L_MODEL_ENABLE_THINKING", raising=False)

    kwargs = get_model_init_kwargs(streaming=False)

    assert "extra_body" not in kwargs
    assert "thinking" not in kwargs
