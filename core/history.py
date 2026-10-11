"""Versioned JSON persistence for classroom rounds and answer timing."""

from __future__ import annotations

import json
import logging
import math
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

from core.models import Grade

if TYPE_CHECKING:
    from core.classroom import AgentRoundRecord, RoundRecord

_LOGGER = logging.getLogger(__name__)
_SCHEMA_VERSION = 1


class HistoryStore:
    """Persist classroom rounds as versioned UTF-8 JSON."""

    def __init__(self, path: str | Path = "results/history.json") -> None:
        """Create a history store for the provided JSON file path."""
        self.path = Path(path)

    def save_round(self, round_record: RoundRecord) -> None:
        """Insert or replace a round record and atomically persist the history."""
        rounds = self.load_rounds()
        for index, existing in enumerate(rounds):
            if existing.round_id == round_record.round_id:
                rounds[index] = round_record
                break
        else:
            rounds.append(round_record)
        self._write(rounds)

    def update_grade(
        self, round_id: str, agent_id: str, grade: Grade, score_after: int
    ) -> None:
        """Update an agent grade in a saved round and persist it.

        Raises:
            KeyError: If the round or agent is not present in history.
            TypeError: If ``grade`` is not a :class:`Grade`.
        """
        if not isinstance(grade, Grade):
            raise TypeError("grade must be a Grade")
        rounds = self.load_rounds()
        for round_record in rounds:
            if round_record.round_id != round_id:
                continue
            for agent_record in round_record.agents:
                if agent_record.agent_id == agent_id:
                    agent_record.state = "answered"
                    agent_record.grade = grade.value
                    agent_record.score_after = score_after
                    self._write(rounds)
                    return
            raise KeyError(agent_id)
        raise KeyError(round_id)

    def load_rounds(self) -> list[RoundRecord]:
        """Load the saved rounds, returning an empty list for absent/bad files."""
        if not self.path.exists():
            return []
        try:
            with self.path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
            if not isinstance(payload, dict):
                raise ValueError("history root must be a JSON object")
            if payload.get("schema_version") != _SCHEMA_VERSION:
                raise ValueError("unsupported history schema version")
            rounds_data = payload.get("rounds")
            if not isinstance(rounds_data, list):
                raise ValueError("history rounds must be a JSON array")
            return [self._round_from_dict(item) for item in rounds_data]
        except (OSError, json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
            _LOGGER.warning("Could not load history from %s: %s", self.path, exc)
            return []

    def load_scores(self) -> dict[str, int]:
        """Return the latest saved cumulative score for each agent."""
        scores: dict[str, int] = {}
        for round_record in self.load_rounds():
            for agent_record in round_record.agents:
                if agent_record.score_after is not None:
                    scores[agent_record.agent_id] = agent_record.score_after
                elif agent_record.grade in (Grade.GOOD.value, Grade.BAD.value):
                    previous_score = scores.get(agent_record.agent_id, 0)
                    scores[agent_record.agent_id] = previous_score + (
                        1 if agent_record.grade == Grade.GOOD.value else -1
                    )
        return scores

    def export_json(self) -> dict[str, object]:
        """Return the current history as a serializable versioned mapping."""
        return {
            "schema_version": _SCHEMA_VERSION,
            "rounds": [asdict(round_record) for round_record in self.load_rounds()],
        }

    def _write(self, rounds: list[RoundRecord]) -> None:
        """Atomically write all round records as UTF-8 JSON."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": _SCHEMA_VERSION,
            "rounds": [asdict(round_record) for round_record in rounds],
        }
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as file:
                temporary_path = Path(file.name)
                json.dump(payload, file, ensure_ascii=False, indent=2)
                file.flush()
                os.fsync(file.fileno())
            temporary_path.replace(self.path)
        except OSError:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _round_from_dict(value: object) -> RoundRecord:
        """Validate one decoded round and rebuild its framework-free records."""
        from core.classroom import RoundRecord

        if not isinstance(value, dict):
            raise ValueError("round record must be a JSON object")
        agents_data = value.get("agents")
        if not isinstance(agents_data, list):
            raise ValueError("round agents must be a JSON array")
        agents = [
            HistoryStore._agent_from_dict(agent_data) for agent_data in agents_data
        ]
        return RoundRecord(
            round_id=HistoryStore._required_string(value, "round_id"),
            question=HistoryStore._required_string(value, "question"),
            started_at=HistoryStore._required_string(value, "started_at"),
            agents=agents,
        )

    @staticmethod
    def _agent_from_dict(value: object) -> AgentRoundRecord:
        """Rebuild a validated per-agent history record."""
        from core.classroom import AgentRoundRecord

        if not isinstance(value, dict):
            raise ValueError("agent record must be a JSON object")
        answer_rank = value.get("answer_rank")
        latency_seconds = value.get("latency_seconds")
        score_after = value.get("score_after")
        if answer_rank is not None and (
            not isinstance(answer_rank, int)
            or isinstance(answer_rank, bool)
            or answer_rank < 1
        ):
            raise ValueError("answer_rank must be a positive integer or null")
        if latency_seconds is not None and (
            not isinstance(latency_seconds, (int, float))
            or isinstance(latency_seconds, bool)
            or not math.isfinite(latency_seconds)
            or latency_seconds < 0
        ):
            raise ValueError("latency_seconds must be finite and non-negative or null")
        if score_after is not None and (
            not isinstance(score_after, int) or isinstance(score_after, bool)
        ):
            raise ValueError("score_after must be an integer or null")
        return AgentRoundRecord(
            agent_id=HistoryStore._required_string(value, "agent_id"),
            state=HistoryStore._required_string(value, "state"),
            answer_text=HistoryStore._optional_string(value, "answer_text"),
            provider=HistoryStore._optional_string(value, "provider"),
            error_message=HistoryStore._optional_string(value, "error_message"),
            grade=HistoryStore._optional_string(value, "grade"),
            score_after=score_after,
            answer_rank=answer_rank,
            latency_seconds=(
                float(latency_seconds) if latency_seconds is not None else None
            ),
        )

    @staticmethod
    def _required_string(value: dict[str, object], key: str) -> str:
        result = value.get(key)
        if not isinstance(result, str):
            raise ValueError(f"{key} must be a string")
        return result

    @staticmethod
    def _optional_string(value: dict[str, object], key: str) -> str | None:
        result = value.get(key)
        if result is not None and not isinstance(result, str):
            raise ValueError(f"{key} must be a string or null")
        return result
