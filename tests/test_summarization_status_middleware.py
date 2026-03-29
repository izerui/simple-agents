from types import SimpleNamespace

from src.middleware.summarization_status import SummarizationStatusMiddleware


def test_get_profile_limit_reads_model_profile():
    middleware = SummarizationStatusMiddleware()
    request = SimpleNamespace(model=SimpleNamespace(profile={"max_input_tokens": 12345}))

    assert middleware._get_profile_limit(request) == 12345


def test_build_counted_messages_prepends_system_message():
    middleware = SummarizationStatusMiddleware()
    system_message = SimpleNamespace()
    user_message = SimpleNamespace()
    request = SimpleNamespace(system_message=system_message, messages=[user_message])

    assert middleware._build_counted_messages(request) == [system_message, user_message]
