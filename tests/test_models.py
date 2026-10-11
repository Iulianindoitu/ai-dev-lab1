"""Tests for framework-independent domain models."""

from dataclasses import FrozenInstanceError

import pytest

from core.models import Agent, AgentState, Answer, Grade


def make_answer(agent_id: str = "chatgpt") -> Answer:
    """Create a valid answer for model tests."""
    return Answer(
        agent_id=agent_id,
        question="Ce este o stea?",
        text="O stea este un corp ceresc.",
        created_at="2026-10-11T14:00:00+03:00",
        provider="mock",
        round_id="round-1",
    )


def make_agent() -> Agent:
    """Create a valid agent for model tests."""
    return Agent(id="chatgpt", name="ChatGPT", color=(40, 80, 120))


def test_agent_initial_state_is_idle() -> None:
    agent = make_agent()

    assert agent.state is AgentState.IDLE
    assert agent.answer is None
    assert agent.error_message is None
    assert agent.graded_round_id is None
    assert agent.score == 0


def test_agent_reset_for_round_clears_round_fields_and_preserves_score() -> None:
    agent = make_agent()
    agent.set_thinking()
    agent.set_ready(make_answer())
    agent.graded_round_id = "round-1"
    agent.answer_rank = 2
    agent.latency_seconds = 1.25
    agent.score = 2

    agent.reset_for_round()

    assert agent.state is AgentState.IDLE
    assert agent.answer is None
    assert agent.error_message is None
    assert agent.graded_round_id is None
    assert agent.answer_rank is None
    assert agent.latency_seconds is None
    assert agent.score == 2


def test_agent_ready_requires_matching_answer() -> None:
    agent = make_agent()
    agent.set_thinking()

    agent.set_ready(make_answer())

    assert agent.state is AgentState.READY
    assert agent.answer == make_answer()
    assert agent.answer_rank is None
    assert agent.latency_seconds is None

    with pytest.raises(ValueError):
        agent.set_ready(make_answer(agent_id="gemini"))


def test_answer_is_immutable_and_rejects_blank_text() -> None:
    answer = make_answer()

    with pytest.raises(FrozenInstanceError):
        answer.text = "modified"  # type: ignore[misc]
    with pytest.raises(ValueError, match="text"):
        Answer(
            agent_id="chatgpt",
            question="Ce este o stea?",
            text="  ",
            created_at="2026-10-11T14:00:00+03:00",
            provider="mock",
            round_id="round-1",
        )


def test_agent_error_stores_message() -> None:
    agent = make_agent()
    agent.set_thinking()

    agent.set_error("Serviciul nu a răspuns.")

    assert agent.state is AgentState.ERROR
    assert agent.error_message == "Serviciul nu a răspuns."
    assert agent.answer is None


def test_invalid_state_transition_is_rejected_without_mutation() -> None:
    agent = make_agent()

    with pytest.raises(ValueError):
        agent.set_ready(make_answer())

    assert agent.state is AgentState.IDLE
    assert agent.answer is None
    assert agent.error_message is None


def test_grade_values_are_available() -> None:
    assert Grade.GOOD.value == "good"
    assert Grade.BAD.value == "bad"
