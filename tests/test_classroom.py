"""Tests for classroom controller and round behavior."""

import threading
import time

import pytest

from core.classroom import Classroom, RoundRecord
from core.models import Agent, AgentState, Grade
from core.scoreboard import Scoreboard
from providers.base import AnswerProvider


class MemoryHistory:
    """In-memory history fake for classroom tests."""

    def __init__(self) -> None:
        self.rounds: dict[str, RoundRecord] = {}
        self.grades: list[tuple[str, str, Grade, int]] = []

    def save_round(self, round_record: RoundRecord) -> None:
        self.rounds[round_record.round_id] = round_record

    def update_grade(
        self, round_id: str, agent_id: str, grade: Grade, score_after: int
    ) -> None:
        self.grades.append((round_id, agent_id, grade, score_after))


class ImmediateProvider(AnswerProvider):
    """Provider fake that returns immediately unless configured to fail."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[str, str]] = []

    def get_answer(self, question: str, agent: Agent) -> str:
        self.calls.append((question, agent.id))
        if self.fail:
            raise RuntimeError("provider failure")
        return f"Răspuns pentru {agent.name}: {question}"


def make_classroom(
    provider: AnswerProvider | None = None,
    *,
    timeout_seconds: float = 1.0,
    max_workers: int = 6,
) -> tuple[Classroom, list[Agent], Scoreboard, MemoryHistory]:
    """Build a small classroom and its observable test dependencies."""
    agents = [
        Agent(id="chatgpt", name="ChatGPT", color=(30, 60, 90)),
        Agent(id="gemini", name="Gemini", color=(90, 60, 30)),
    ]
    scoreboard = Scoreboard(agents)
    history = MemoryHistory()
    classroom = Classroom(
        agents,
        provider or ImmediateProvider(),
        scoreboard,
        history,
        timeout_seconds=timeout_seconds,
        max_workers=max_workers,
    )
    return classroom, agents, scoreboard, history


def wait_for_states(
    classroom: Classroom, agents: list[Agent], state: AgentState
) -> None:
    """Poll asynchronously until each agent reaches a target state."""
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        classroom.poll()
        if all(agent.state is state for agent in agents):
            return
        time.sleep(0.002)
    pytest.fail(f"agents did not reach {state.value}")


def test_ask_starts_round_and_requests_all_agents() -> None:
    provider = ImmediateProvider()
    classroom, agents, _, history = make_classroom(provider)
    try:
        round_id = classroom.ask("Ce înseamnă gravitația?")

        assert round_id
        assert classroom.get_round_id() == round_id
        assert all(agent.state is AgentState.THINKING for agent in agents)
        wait_for_states(classroom, agents, AgentState.READY)
        assert sorted(agent_id for _, agent_id in provider.calls) == [
            "chatgpt",
            "gemini",
        ]
        assert all(agent.answer and agent.answer.round_id == round_id for agent in agents)
        assert round_id in history.rounds
    finally:
        classroom.close()


def test_provider_requests_run_concurrently() -> None:
    barrier = threading.Barrier(2)

    class ConcurrentProvider(AnswerProvider):
        def get_answer(self, question: str, agent: Agent) -> str:
            barrier.wait(timeout=1)
            return f"Răspuns pentru {agent.name}: {question}"

    classroom, agents, _, _ = make_classroom(
        ConcurrentProvider(), max_workers=2
    )
    try:
        classroom.ask("Întrebare")
        wait_for_states(classroom, agents, AgentState.READY)
    finally:
        classroom.close()


def test_empty_question_does_not_start_a_round_or_submit_work() -> None:
    provider = ImmediateProvider()
    classroom, agents, _, _ = make_classroom(provider)
    try:
        for question in ("", "  \t"):
            with pytest.raises(ValueError):
                classroom.ask(question)

        assert classroom.get_round_id() is None
        assert all(agent.state is AgentState.IDLE for agent in agents)
        assert provider.calls == []
    finally:
        classroom.close()


def test_provider_failure_moves_agent_to_error() -> None:
    classroom, agents, _, _ = make_classroom(ImmediateProvider(fail=True))
    try:
        classroom.ask("Întrebare")
        wait_for_states(classroom, agents, AgentState.ERROR)
        assert all(agent.error_message for agent in agents)
    finally:
        classroom.close()


def test_results_from_old_round_are_ignored() -> None:
    first_started = threading.Event()
    release_first = threading.Event()

    class DelayedFirstProvider(AnswerProvider):
        def get_answer(self, question: str, agent: Agent) -> str:
            if question == "prima":
                first_started.set()
                assert release_first.wait(timeout=2)
            return f"{question} pentru {agent.name}"

    classroom, agents, _, _ = make_classroom(
        DelayedFirstProvider(), max_workers=2
    )
    try:
        old_round_id = classroom.ask("prima")
        assert first_started.wait(timeout=1)
        new_round_id = classroom.ask("a doua")
        release_first.set()
        wait_for_states(classroom, agents, AgentState.READY)

        assert new_round_id != old_round_id
        assert all(agent.answer is not None for agent in agents)
        assert all(agent.answer.round_id == new_round_id for agent in agents)
        assert all(agent.answer.question == "a doua" for agent in agents)
    finally:
        release_first.set()
        classroom.close()


def test_poll_marks_expired_requests_error_without_waiting_for_provider() -> None:
    release_provider = threading.Event()

    class BlockingProvider(AnswerProvider):
        def get_answer(self, question: str, agent: Agent) -> str:
            release_provider.wait(timeout=2)
            return f"prea târziu: {question}, {agent.name}"

    classroom, agents, _, _ = make_classroom(
        BlockingProvider(), timeout_seconds=0.02
    )
    try:
        classroom.ask("întrebare")
        time.sleep(0.03)
        started_at = time.monotonic()

        classroom.poll()

        elapsed = time.monotonic() - started_at
        assert elapsed < 0.1
        assert all(agent.state is AgentState.ERROR for agent in agents)
        assert all("expirat" in agent.error_message for agent in agents)
    finally:
        release_provider.set()
        classroom.close()


def test_late_result_does_not_overwrite_timeout_error() -> None:
    release_provider = threading.Event()

    class BlockingProvider(AnswerProvider):
        def get_answer(self, question: str, agent: Agent) -> str:
            assert release_provider.wait(timeout=2)
            return f"răspuns întârziat: {question}, {agent.name}"

    classroom, agents, _, _ = make_classroom(
        BlockingProvider(), timeout_seconds=0.02
    )
    try:
        classroom.ask("întrebare")
        time.sleep(0.03)
        classroom.poll()
        errors = [agent.error_message for agent in agents]
        release_provider.set()
        time.sleep(0.02)

        assert classroom.poll() == []
        assert all(agent.state is AgentState.ERROR for agent in agents)
        assert [agent.error_message for agent in agents] == errors
    finally:
        release_provider.set()
        classroom.close()


def test_only_ready_selected_agent_can_be_graded_once() -> None:
    classroom, agents, scoreboard, history = make_classroom()
    try:
        round_id = classroom.ask("Întrebare")
        wait_for_states(classroom, agents, AgentState.READY)
        with pytest.raises(ValueError):
            classroom.grade(agents[0].id, Grade.GOOD)

        selected = classroom.select(agents[0].id)
        assert selected is agents[0]
        assert scoreboard.get_score(agents[0].id) == 0
        assert classroom.grade(agents[0].id, Grade.GOOD) == 1
        assert agents[0].state is AgentState.ANSWERED
        assert agents[0].graded_round_id == round_id
        assert scoreboard.get_score(agents[0].id) == 1
        assert history.grades == [(round_id, agents[0].id, Grade.GOOD, 1)]

        with pytest.raises(ValueError):
            classroom.grade(agents[0].id, Grade.BAD)
        assert scoreboard.get_score(agents[0].id) == 1
    finally:
        classroom.close()


def test_select_rejects_unknown_or_non_ready_agent() -> None:
    classroom, _, _, _ = make_classroom()
    try:
        with pytest.raises(KeyError):
            classroom.select("unknown")
        classroom.ask("Întrebare")
        with pytest.raises(ValueError):
            classroom.select("chatgpt")
    finally:
        classroom.close()


def test_new_round_resets_round_state_and_preserves_scores() -> None:
    classroom, agents, scoreboard, _ = make_classroom()
    try:
        classroom.ask("prima întrebare")
        wait_for_states(classroom, agents, AgentState.READY)
        classroom.select("chatgpt")
        classroom.grade("chatgpt", Grade.BAD)
        old_score = scoreboard.get_score("chatgpt")

        classroom.ask("întrebarea următoare")

        assert scoreboard.get_score("chatgpt") == old_score
        assert all(agent.state is AgentState.THINKING for agent in agents)
        assert all(agent.answer is None for agent in agents)
        assert all(agent.graded_round_id is None for agent in agents)
        assert classroom.get_selected_agent() is None
    finally:
        classroom.close()


def test_close_rejects_new_rounds() -> None:
    classroom, _, _, _ = make_classroom()
    classroom.close()

    with pytest.raises(RuntimeError, match="închis"):
        classroom.ask("întrebare")
