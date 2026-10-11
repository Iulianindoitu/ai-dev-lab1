"""Tests for the offline mock answer provider."""

import re

import pytest

from core.models import Agent
from providers.base import AnswerProvider, ProviderError, ProviderTimeoutError
from providers.mock import MockProvider, classify_question


def make_agent(agent_id: str = "chatgpt") -> Agent:
    """Create an agent for provider tests."""
    return Agent(id=agent_id, name=agent_id.title(), color=(10, 20, 30))


def test_answer_provider_is_an_abstract_interface() -> None:
    with pytest.raises(TypeError):
        AnswerProvider()


def test_provider_timeout_error_is_a_provider_error() -> None:
    assert issubclass(ProviderTimeoutError, ProviderError)


def test_provider_is_identified_as_mock() -> None:
    assert MockProvider(min_delay=0, max_delay=0).name == "mock"


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
    assert all("demonstrativ mock" not in answer for answer in first_answers)
    assert all(answer.strip() for answer in first_answers)


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

    assert "întrebare" in answer.casefold()


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

    good_text = correct_only.get_answer("De ce contează energia?", make_agent())
    misleading_text = misleading_only.get_answer("De ce contează energia?", make_agent())

    assert "energia" in good_text
    assert any(
        cue in misleading_text.casefold()
        for cue in ("marțienii", "girafă", "luna")
    )
    assert "intenționat posibil incorect" not in good_text
    assert "intenționat posibil incorect" not in misleading_text


def test_personalities_produce_distinct_natural_styles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("providers.mock.time.sleep", lambda _: None)
    provider = MockProvider(
        seed=2,
        min_delay=0,
        max_delay=0,
        wrong_answer_probability=0,
    )

    answers = {
        agent_id: provider.get_answer("Cum învățăm despre energie?", make_agent(agent_id))
        for agent_id in ("chatgpt", "gemini", "copilot", "grok", "claude", "deepseek")
    }

    assert len(set(answers.values())) == len(answers)
    assert "energie" in answers["chatgpt"]
    assert "uite ce interesant" in answers["gemini"].casefold()
    assert "practic," in answers["copilot"].casefold()
    assert "sincer," in answers["grok"].casefold()
    assert "din câte văd" in answers["claude"].casefold()
    assert "pe scurt," in answers["deepseek"].casefold()


def test_personal_answers_sound_conversational_not_like_provider_disclaimers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("providers.mock.time.sleep", lambda _: None)
    provider = MockProvider(seed=9, min_delay=0, max_delay=0, wrong_answer_probability=0)

    answer = provider.get_answer(
        "Ce părere aveți despre roboți?",
        make_agent("claude"),
    ).casefold()

    assert "roboți" in answer
    assert "nu am opinii" not in answer
    assert "ca sistem ai" not in answer
    assert any(
        cue in answer
        for cue in ("depinde", "exemplu concret", "mai multe puncte de vedere")
    )


@pytest.mark.parametrize("wrong_probability", [0, 1])
def test_every_personality_and_category_returns_two_to_four_sentences(
    monkeypatch: pytest.MonkeyPatch,
    wrong_probability: float,
) -> None:
    monkeypatch.setattr("providers.mock.time.sleep", lambda _: None)
    questions = (
        "Salut!",
        "Ce părere aveți despre energie?",
        "Ce este energia?",
        "De ce contează energia?",
        "Cum folosim energia?",
        "Câtă energie folosim?",
        "Energia e mai bună sau apa?",
        "Există energie?",
        "Explică energia?",
    )
    agent_ids = ("chatgpt", "gemini", "copilot", "grok", "claude", "deepseek")
    provider = MockProvider(
        seed=43,
        min_delay=0,
        max_delay=0,
        wrong_answer_probability=wrong_probability,
    )

    for question in questions:
        for agent_id in agent_ids:
            answer = provider.get_answer(question, make_agent(agent_id))
            sentence_count = len(re.findall(r"[.!?](?:\s|$)", answer))
            assert 2 <= sentence_count <= 4, (question, agent_id, answer)


@pytest.mark.parametrize(
    ("question", "category", "topic"),
    [
        ("Bună, tuturor!", "greeting", "tuturor"),
        ("Ce părere aveți despre roboți?", "personal", "despre roboți"),
        ("Ce înseamnă energia?", "definition", "energia"),
        ("  Ce   este   energia?  ", "definition", "energia"),
        ("De ce plouă?", "why", "plouă"),
        ("Cum funcționează motorul?", "how", "funcționează motorul"),
        ("Câtă apă bem?", "quantity", "apă bem"),
        ("Este energia mai utilă sau apa?", "comparison", "energia mai utilă sau apa"),
        ("Există viață pe Marte?", "yes_no", "viață pe Marte"),
        ("Spune-mi despre planete?", "other", "Spune-mi despre planete"),
    ],
)
def test_question_classification_and_topic_extraction(
    question: str,
    category: str,
    topic: str,
) -> None:
    actual_category, actual_topic = classify_question(question)

    assert actual_category == category
    assert actual_topic.casefold() == topic.casefold()


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
