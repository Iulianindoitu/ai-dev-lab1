"""Tests for the offline mock answer provider."""

import pytest

from core.models import Agent
from providers.base import AnswerProvider, ProviderError, ProviderTimeoutError
from providers.mock import MockProvider


def make_agent(agent_id: str = "chatgpt") -> Agent:
    """Create an agent for provider tests."""
    return Agent(id=agent_id, name=agent_id.title(), color=(10, 20, 30))


def test_answer_provider_is_an_abstract_interface() -> None:
    with pytest.raises(TypeError):
        AnswerProvider()


def test_provider_timeout_error_is_a_provider_error() -> None:
    assert issubclass(ProviderTimeoutError, ProviderError)


def test_seed_makes_answers_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("providers.mock.time.sleep", lambda _: None)
    first = MockProvider(
        seed=42,
        min_delay=0,
        max_delay=0,
        wrong_answer_probability=0.5,
    )
    second = MockProvider(
        seed=42,
        min_delay=0,
        max_delay=0,
        wrong_answer_probability=0.5,
    )
    agent = make_agent()

    first_answers = [first.get_answer("Ce este energia?", agent) for _ in range(5)]
    second_answers = [second.get_answer("Ce este energia?", agent) for _ in range(5)]

    assert first_answers == second_answers
    assert all("demonstrativ mock" in answer for answer in first_answers)


def test_delay_is_selected_from_configured_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delays: list[float] = []
    monkeypatch.setattr("providers.mock.time.sleep", delays.append)
    provider = MockProvider(
        seed=7,
        min_delay=0.1,
        max_delay=0.3,
        wrong_answer_probability=0,
    )

    provider.get_answer("Întrebare?", make_agent())

    assert len(delays) == 1
    assert 0.1 <= delays[0] <= 0.3


def test_zero_delay_does_not_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_sleep(_: float) -> None:
        pytest.fail("zero-delay provider should not sleep")

    monkeypatch.setattr("providers.mock.time.sleep", unexpected_sleep)
    provider = MockProvider(min_delay=0, max_delay=0)

    answer = provider.get_answer("Întrebare?", make_agent())

    assert "Întrebare?" in answer


def test_misleading_answers_are_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("providers.mock.time.sleep", lambda _: None)
    correct_only = MockProvider(
        seed=1,
        min_delay=0,
        max_delay=0,
        wrong_answer_probability=0,
    )
    misleading_only = MockProvider(
        seed=1,
        min_delay=0,
        max_delay=0,
        wrong_answer_probability=1,
    )

    good_text = correct_only.get_answer("De ce?", make_agent())
    misleading_text = misleading_only.get_answer("De ce?", make_agent())

    assert "intenționat posibil incorect" not in good_text
    assert "intenționat posibil incorect" in misleading_text


def test_agent_styles_are_varied_without_changing_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("providers.mock.time.sleep", lambda _: None)
    provider = MockProvider(
        seed=2,
        min_delay=0,
        max_delay=0,
        wrong_answer_probability=0,
    )

    chatgpt_answer = provider.get_answer("Întrebare?", make_agent("chatgpt"))
    gemini_answer = provider.get_answer("Întrebare?", make_agent("gemini"))

    assert "Chatgpt" in chatgpt_answer
    assert "Gemini" in gemini_answer
    assert "Pe scurt" in chatgpt_answer
    assert "Să privim întrebarea astfel" in gemini_answer


@pytest.mark.parametrize(
    ("kwargs", "exception"),
    [
        ({"min_delay": -0.1}, ValueError),
        ({"min_delay": 2, "max_delay": 1}, ValueError),
        ({"min_delay": float("inf")}, ValueError),
        ({"wrong_answer_probability": -0.1}, ValueError),
        ({"wrong_answer_probability": 1.1}, ValueError),
        ({"seed": 1.5}, TypeError),
    ],
)
def test_invalid_configuration_is_rejected(
    kwargs: dict[str, object], exception: type[Exception]
) -> None:
    with pytest.raises(exception):
        MockProvider(**kwargs)  # type: ignore[arg-type]


def test_empty_question_is_rejected() -> None:
    provider = MockProvider(min_delay=0, max_delay=0)

    with pytest.raises(ValueError, match="empty"):
        provider.get_answer("  ", make_agent())
