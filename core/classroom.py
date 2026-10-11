"""Classroom controller for rounds, provider work, deadlines, and grading."""

from __future__ import annotations

import logging
import math
import queue
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from core.models import Agent, AgentState, Answer, Grade
from core.scoreboard import Scoreboard
from providers.base import AnswerProvider, ProviderError

_LOGGER = logging.getLogger(__name__)
_TIMEOUT_MESSAGE = "Timpul pentru generarea răspunsului a expirat."
_PROVIDER_ERROR_MESSAGE = "Nu s-a putut genera un răspuns pentru acest elev."
_CLOSED_MESSAGE = "Clasa este închisă și nu mai acceptă solicitări."


@dataclass
class AgentRoundRecord:
    """Persistable outcome and grade for one agent in a round."""

    agent_id: str
    state: str
    answer_text: str | None = None
    provider: str | None = None
    error_message: str | None = None
    grade: str | None = None
    score_after: int | None = None


@dataclass
class RoundRecord:
    """Persistable question and agent outcomes for one classroom round."""

    round_id: str
    question: str
    started_at: str
    agents: list[AgentRoundRecord]


class HistoryStore(Protocol):
    """Persistence interface used by the classroom controller."""

    def save_round(self, round_record: RoundRecord) -> None:
        """Save or replace a round's current record."""
        ...

    def update_grade(
        self, round_id: str, agent_id: str, grade: Grade, score_after: int
    ) -> None:
        """Persist the grade and resulting score for an agent."""
        ...


@dataclass(frozen=True)
class AnswerResult:
    """Immutable provider result transferred to the controller via a queue."""

    round_id: str
    agent_id: str
    answer: Answer | None
    error_message: str | None
    completed_at: float

    def __post_init__(self) -> None:
        """Reject malformed result records at their construction boundary."""
        if not isinstance(self.round_id, str) or not self.round_id:
            raise ValueError("round_id must be a non-empty string")
        if not isinstance(self.agent_id, str) or not self.agent_id:
            raise ValueError("agent_id must be a non-empty string")
        if (self.answer is None) == (self.error_message is None):
            raise ValueError("exactly one of answer and error_message is required")
        if self.answer is not None and not isinstance(self.answer, Answer):
            raise TypeError("answer must be an Answer or None")
        if self.error_message is not None and (
            not isinstance(self.error_message, str) or not self.error_message.strip()
        ):
            raise ValueError("error_message must be a non-empty string")
        if (
            not isinstance(self.completed_at, (int, float))
            or isinstance(self.completed_at, bool)
            or not math.isfinite(self.completed_at)
        ):
            raise ValueError("completed_at must be a finite monotonic timestamp")


class Classroom:
    """Coordinate classroom state on the main thread and provider work in workers."""

    def __init__(
        self,
        agents: list[Agent],
        provider: AnswerProvider,
        scoreboard: Scoreboard,
        history: HistoryStore,
        timeout_seconds: float = 30.0,
        max_workers: int = 6,
    ) -> None:
        """Create a classroom controller and its provider worker pool.

        Args:
            agents: Students in their stable display and ranking order.
            provider: Provider used to request each student's answer.
            scoreboard: Scoreboard registered for exactly these students.
            history: Store used to persist round and grading data.
            timeout_seconds: Per-agent deadline measured from task submission.
            max_workers: Maximum number of concurrent provider calls.

        Raises:
            TypeError: If constructor arguments have invalid types.
            ValueError: If the agent list or timing configuration is invalid.
        """
        if not isinstance(agents, list) or any(
            not isinstance(agent, Agent) for agent in agents
        ):
            raise TypeError("agents must be a list of Agent instances")
        if not agents:
            raise ValueError("at least one agent is required")
        agent_ids = [agent.id for agent in agents]
        if len(set(agent_ids)) != len(agent_ids):
            raise ValueError("agent IDs must be unique")
        if not isinstance(provider, AnswerProvider):
            raise TypeError("provider must implement AnswerProvider")
        if not isinstance(scoreboard, Scoreboard):
            raise TypeError("scoreboard must be a Scoreboard")
        if not callable(getattr(history, "save_round", None)) or not callable(
            getattr(history, "update_grade", None)
        ):
            raise TypeError("history must implement save_round and update_grade")
        if (
            not isinstance(timeout_seconds, (int, float))
            or isinstance(timeout_seconds, bool)
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be a finite positive number")
        if not isinstance(max_workers, int) or isinstance(max_workers, bool):
            raise TypeError("max_workers must be an integer")
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")
        for agent_id in agent_ids:
            try:
                scoreboard.get_score(agent_id)
            except KeyError as exc:
                raise ValueError(
                    f"scoreboard is missing registered agent {agent_id!r}"
                ) from exc

        self._agents = list(agents)
        self._agents_by_id = {agent.id: agent for agent in agents}
        self._provider = provider
        self._scoreboard = scoreboard
        self._history = history
        self._timeout_seconds = float(timeout_seconds)
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._results: queue.Queue[AnswerResult] = queue.Queue()
        self._deadlines: dict[tuple[str, str], float] = {}
        self._round_id: str | None = None
        self._round_record: RoundRecord | None = None
        self._selected_agent_id: str | None = None
        self._closed = False

    def ask(self, question: str) -> str:
        """Begin a round and submit one independent answer task per agent.

        Raises:
            TypeError: If ``question`` is not a string.
            ValueError: If ``question`` is empty or whitespace-only.
            RuntimeError: If the classroom has been closed.
        """
        if not isinstance(question, str):
            raise TypeError("question must be a string")
        if not question.strip():
            raise ValueError("question must not be empty")
        if self._closed:
            raise RuntimeError(_CLOSED_MESSAGE)

        normalized_question = question.strip()
        round_id = str(uuid4())
        started_at = datetime.now(timezone.utc).isoformat()
        for agent in self._agents:
            agent.set_thinking()
        self._round_id = round_id
        self._selected_agent_id = None
        self._round_record = RoundRecord(
            round_id=round_id,
            question=normalized_question,
            started_at=started_at,
            agents=[
                AgentRoundRecord(agent_id=agent.id, state=AgentState.THINKING.value)
                for agent in self._agents
            ],
        )

        self._discard_queued_results()
        self._deadlines.clear()
        for agent in self._agents:
            deadline_key = (round_id, agent.id)
            submitted_at = time.monotonic()
            self._deadlines[deadline_key] = submitted_at + self._timeout_seconds
            try:
                self._executor.submit(
                    self._run_provider, round_id, normalized_question, agent
                )
            except RuntimeError:
                self._results.put(
                    AnswerResult(
                        round_id=round_id,
                        agent_id=agent.id,
                        answer=None,
                        error_message=_PROVIDER_ERROR_MESSAGE,
                        completed_at=time.monotonic(),
                    )
                )

        self._save_round()
        return round_id

    def poll_results(self) -> list[AnswerResult]:
        """Drain completed results without blocking and apply valid state changes.

        Results from older rounds, unknown agents, timed-out requests, or
        agents no longer in THINKING are ignored.
        """
        if self._round_id is None:
            return []

        applied: list[AnswerResult] = []
        history_changed = False
        while True:
            try:
                result = self._results.get_nowait()
            except queue.Empty:
                break
            if result.round_id != self._round_id:
                continue
            agent = self._agents_by_id.get(result.agent_id)
            if agent is None or agent.state is not AgentState.THINKING:
                continue
            deadline = self._deadlines.get((result.round_id, result.agent_id))
            if deadline is None or result.completed_at > deadline:
                continue

            record = self._get_agent_record(agent.id)
            if result.answer is not None:
                answer = result.answer
                if (
                    answer.agent_id != agent.id
                    or answer.round_id != self._round_id
                    or not answer.text.strip()
                ):
                    agent.set_error(_PROVIDER_ERROR_MESSAGE)
                    record.state = AgentState.ERROR.value
                    record.error_message = _PROVIDER_ERROR_MESSAGE
                else:
                    agent.set_ready(answer)
                    record.state = AgentState.READY.value
                    record.answer_text = answer.text
                    record.provider = answer.provider
            else:
                error_message = result.error_message or _PROVIDER_ERROR_MESSAGE
                agent.set_error(error_message)
                record.state = AgentState.ERROR.value
                record.error_message = error_message

            self._deadlines.pop((result.round_id, result.agent_id), None)
            applied.append(result)
            history_changed = True

        now = time.monotonic()
        for agent in self._agents:
            deadline_key = (self._round_id, agent.id)
            deadline = self._deadlines.get(deadline_key)
            if (
                agent.state is AgentState.THINKING
                and deadline is not None
                and now >= deadline
            ):
                agent.set_error(_TIMEOUT_MESSAGE)
                record = self._get_agent_record(agent.id)
                record.state = AgentState.ERROR.value
                record.error_message = _TIMEOUT_MESSAGE
                self._deadlines.pop(deadline_key, None)
                history_changed = True

        if history_changed:
            self._save_round()
        return applied

    def poll(self) -> list[AnswerResult]:
        """Alias for :meth:`poll_results` for frame-loop polling."""
        return self.poll_results()

    def select(self, agent_id: str) -> Agent:
        """Select a READY agent without changing its score.

        Raises:
            KeyError: If ``agent_id`` is unknown.
            ValueError: If the agent is not READY.
        """
        agent = self._agents_by_id[agent_id]
        if agent.state is not AgentState.READY:
            raise ValueError(f"agent {agent_id!r} is not READY")
        self._selected_agent_id = agent_id
        return agent

    def grade(self, agent_id: str, grade: Grade) -> int:
        """Grade the currently selected READY agent exactly once this round.

        Raises:
            KeyError: If ``agent_id`` is unknown.
            TypeError: If ``grade`` is not a :class:`Grade`.
            ValueError: If the agent is not selected and READY in an active round.
        """
        agent = self._agents_by_id[agent_id]
        if not isinstance(grade, Grade):
            raise TypeError("grade must be a Grade")
        if self._round_id is None:
            raise ValueError("there is no active round")
        if self._selected_agent_id != agent_id:
            raise ValueError("only the selected agent can be graded")
        if agent.state is not AgentState.READY:
            raise ValueError("only a READY agent can be graded")
        if agent.graded_round_id == self._round_id:
            raise ValueError("agent has already been graded this round")

        score = self._scoreboard.add_grade(agent_id, grade)
        agent.score = score
        agent.state = AgentState.ANSWERED
        agent.graded_round_id = self._round_id
        record = self._get_agent_record(agent_id)
        record.state = AgentState.ANSWERED.value
        record.grade = grade.value
        record.score_after = score
        try:
            self._history.update_grade(self._round_id, agent_id, grade, score)
        except Exception:
            _LOGGER.exception(
                "Could not persist grade for agent %s in round %s",
                agent_id,
                self._round_id,
            )
        self._save_round()
        return score

    def get_selected_agent(self) -> Agent | None:
        """Return the selected student, if one is selected."""
        if self._selected_agent_id is None:
            return None
        return self._agents_by_id[self._selected_agent_id]

    def get_agents(self) -> list[Agent]:
        """Return a copy of the configured student list."""
        return list(self._agents)

    def get_scoreboard(self) -> Scoreboard:
        """Return this classroom's scoreboard."""
        return self._scoreboard

    def get_round_id(self) -> str | None:
        """Return the active round ID, if a round has started."""
        return self._round_id

    def close(self) -> None:
        """Stop accepting new rounds and cancel queued work without waiting.

        Running provider calls are not interrupted; providers must use finite
        transport timeouts because Python cannot safely stop a running thread.
        """
        if self._closed:
            return
        self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _run_provider(
        self, round_id: str, question: str, agent: Agent
    ) -> AnswerResult:
        """Execute a provider request and transfer its result through the queue."""
        try:
            text = self._provider.get_answer(question, agent)
            if not isinstance(text, str) or not text.strip():
                raise ProviderError("Provider returned an empty answer.")
            provider_name = type(self._provider).__name__.lower()
            if provider_name.endswith("provider"):
                provider_name = provider_name[: -len("provider")]
            answer = Answer(
                agent_id=agent.id,
                question=question,
                text=text,
                created_at=datetime.now(timezone.utc).isoformat(),
                provider=provider_name or "provider",
                round_id=round_id,
            )
            result = AnswerResult(
                round_id=round_id,
                agent_id=agent.id,
                answer=answer,
                error_message=None,
                completed_at=time.monotonic(),
            )
        except Exception as exc:
            if isinstance(exc, ProviderError):
                error_message = str(exc).strip() or _PROVIDER_ERROR_MESSAGE
            else:
                _LOGGER.exception("Provider request failed for agent %s", agent.id)
                error_message = _PROVIDER_ERROR_MESSAGE
            result = AnswerResult(
                round_id=round_id,
                agent_id=agent.id,
                answer=None,
                error_message=error_message,
                completed_at=time.monotonic(),
            )
        self._results.put(result)
        return result

    def _discard_queued_results(self) -> None:
        """Drop results from the previously active round before starting anew."""
        while True:
            try:
                self._results.get_nowait()
            except queue.Empty:
                return

    def _get_agent_record(self, agent_id: str) -> AgentRoundRecord:
        """Find an agent's record in the current round."""
        if self._round_record is None:
            raise RuntimeError("there is no active round record")
        for record in self._round_record.agents:
            if record.agent_id == agent_id:
                return record
        raise KeyError(agent_id)

    def _save_round(self) -> None:
        """Persist the current round while keeping history errors non-fatal."""
        if self._round_record is None:
            return
        try:
            self._history.save_round(self._round_record)
        except Exception:
            _LOGGER.exception("Could not persist round %s", self._round_record.round_id)
