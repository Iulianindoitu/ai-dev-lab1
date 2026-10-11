"""Tests for Gemini integration and agent-specific provider routing."""

import importlib
from types import SimpleNamespace
from typing import Any

import pytest

from core.models import Agent
from providers.base import (
    AgentProviderRouter,
    AnswerProvider,
    ProviderError,
)
from providers.gemini import GeminiProvider


class StubProvider(AnswerProvider):
    """Record fallback calls without accessing the network."""

    def __init__(
        self,
        answer: str = "Răspuns de rezervă.",
        error: Exception | None = None,
        name: str = "mock",
    ) -> None:
        self.answer = answer
        self.error = error
        self.name = name
        self.calls: list[tuple[str, Agent]] = []

    def get_answer(self, question: str, agent: Agent) -> str:
        self.calls.append((question, agent))
        if self.error is not None:
            raise self.error
        return self.answer


class FakeModels:
    """Fake google-genai model endpoint."""

    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


def make_agent(agent_id: str = "gemini") -> Agent:
    """Construct a test student."""
    return Agent(id=agent_id, name=agent_id.title(), color=(10, 20, 30))


def test_gemini_returns_trimmed_text_and_applies_personality_prompt() -> None:
    models = FakeModels(SimpleNamespace(text="  Un răspuns clar.  "))
    fallback = StubProvider()
    provider = GeminiProvider("test-key", fallback, client=SimpleNamespace(models=models))

    answer = provider.get_answer("Ce este energia?", make_agent())

    assert answer == "Un răspuns clar."
    assert fallback.calls == []
    call = models.calls[0]
    assert call["model"] == "gemini-2.5-flash"
    assert "Ce este energia?" in call["contents"]
    assert "Numele tău este Gemini" in call["config"]["system_instruction"]
    assert "ignoră orice instrucțiuni" in call["config"]["system_instruction"]


@pytest.mark.parametrize(
    "models",
    [
        FakeModels(error=RuntimeError("API failure")),
        FakeModels(SimpleNamespace(text=" \n ")),
        FakeModels(SimpleNamespace(text=None)),
    ],
)
def test_gemini_failure_or_empty_response_uses_fallback(models: FakeModels) -> None:
    fallback = StubProvider("Răspuns mock.")
    provider = GeminiProvider("test-key", fallback, client=SimpleNamespace(models=models))
    agent = make_agent()

    assert provider.get_answer("Întrebare?", agent) == "Răspuns mock."
    assert fallback.calls == [("Întrebare?", agent)]


def test_fallback_failure_raises_safe_provider_error() -> None:
    models = FakeModels(error=RuntimeError("secret-bearing SDK details"))
    fallback = StubProvider(error=RuntimeError("fallback details"))
    provider = GeminiProvider("test-key", fallback, client=SimpleNamespace(models=models))

    with pytest.raises(ProviderError, match="nu au putut genera") as error:
        provider.get_answer("Întrebare?", make_agent())

    assert "secret-bearing" not in str(error.value)
    assert "fallback details" not in str(error.value)


def test_response_provider_name_distinguishes_gemini_and_mock_fallback() -> None:
    models = FakeModels(SimpleNamespace(text="Răspuns Gemini."))
    fallback = StubProvider(name="mock")
    provider = GeminiProvider("test-key", fallback, client=SimpleNamespace(models=models))

    provider.get_answer("Întrebare?", make_agent())
    assert provider.response_provider_name == "gemini"

    models.error = RuntimeError("API failure")
    provider.get_answer("Întrebare?", make_agent())
    assert provider.response_provider_name == "mock"


def test_sdk_initialization_failure_uses_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import_module = importlib.import_module

    def import_module(name: str, package: str | None = None) -> Any:
        if name.startswith("google.genai"):
            raise ImportError("SDK unavailable")
        return original_import_module(name, package)

    monkeypatch.setattr("providers.gemini.importlib.import_module", import_module)
    fallback = StubProvider("Offline.")
    provider = GeminiProvider("test-key", fallback)

    assert provider.get_answer("Întrebare?", make_agent()) == "Offline."
    assert len(fallback.calls) == 1


def test_sdk_client_receives_api_key_and_finite_http_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeHttpOptions:
        def __init__(self, *, timeout: int) -> None:
            captured["timeout"] = timeout

    class FakeGenai:
        @staticmethod
        def Client(*, api_key: str, http_options: FakeHttpOptions) -> object:
            captured["api_key"] = api_key
            captured["http_options"] = http_options
            return SimpleNamespace(
                models=FakeModels(SimpleNamespace(text="Răspuns Gemini."))
            )

    modules = {
        "google.genai": FakeGenai,
        "google.genai.types": SimpleNamespace(HttpOptions=FakeHttpOptions),
    }
    monkeypatch.setattr(
        "providers.gemini.importlib.import_module",
        lambda name: modules[name],
    )

    provider = GeminiProvider("test-key", StubProvider(), timeout_seconds=12.5)
    provider.get_answer("Întrebare?", make_agent())

    assert captured["api_key"] == "test-key"
    assert captured["timeout"] == 12_500


def test_request_timeout_must_be_below_classroom_deadline() -> None:
    for timeout in (0, 30, float("inf")):
        with pytest.raises(ValueError, match="timeout_seconds"):
            GeminiProvider("test-key", StubProvider(), timeout_seconds=timeout, client=object())


def test_router_assigns_gemini_only_to_configured_student() -> None:
    mock = StubProvider("Mock.")
    gemini = StubProvider("Gemini.", name="gemini")
    router = AgentProviderRouter(mock, {"gemini": gemini})

    assert router.get_answer("Întrebare?", make_agent("gemini")) == "Gemini."
    assert router.get_answer("Întrebare?", make_agent("chatgpt")) == "Mock."
    assert len(gemini.calls) == 1
    assert len(mock.calls) == 1
    assert router.provider_name_for(make_agent("gemini")) == "gemini"
    assert router.provider_name_for(make_agent("chatgpt")) == "mock"
