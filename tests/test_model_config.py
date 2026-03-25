from src.utils.model_config import get_model_init_kwargs


def test_openai_provider_disables_thinking_by_default(monkeypatch):
    monkeypatch.setenv("L_MODEL_PROVIDER", "openai")
    monkeypatch.delenv("L_MODEL_ENABLE_THINKING", raising=False)

    kwargs = get_model_init_kwargs(streaming=True)

    assert kwargs["extra_body"] == {"enable_thinking": False}


def test_openai_provider_allows_explicit_thinking_override(monkeypatch):
    monkeypatch.setenv("L_MODEL_PROVIDER", "openai")
    monkeypatch.setenv("L_MODEL_ENABLE_THINKING", "true")

    kwargs = get_model_init_kwargs(streaming=True)

    assert "extra_body" not in kwargs


def test_non_openai_provider_does_not_inject_extra_body(monkeypatch):
    monkeypatch.setenv("L_MODEL_PROVIDER", "anthropic")
    monkeypatch.delenv("L_MODEL_ENABLE_THINKING", raising=False)

    kwargs = get_model_init_kwargs(streaming=False)

    assert "extra_body" not in kwargs
