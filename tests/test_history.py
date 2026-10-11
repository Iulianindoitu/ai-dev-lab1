"""Tests for classroom history persistence."""

import json
from pathlib import Path

from core.classroom import AgentRoundRecord, RoundRecord
from core.history import HistoryStore
from core.models import Grade


def make_round() -> RoundRecord:
    """Create a round with answer ordering and latency metadata."""
    return RoundRecord(
        round_id="round-1",
        question="Ce înseamnă școală?",
        started_at="2026-10-11T15:00:00+03:00",
        agents=[
            AgentRoundRecord(
                agent_id="gemini",
                state="ready",
                answer_text="Un răspuns.",
                provider="mock",
                answer_rank=1,
                latency_seconds=0.3125,
            ),
            AgentRoundRecord(
                agent_id="chatgpt",
                state="error",
                error_message="Timeout",
            ),
        ],
    )


def test_save_and_load_round_preserves_answer_rank_and_latency(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.json"
    history = HistoryStore(path)

    history.save_round(make_round())
    loaded = history.load_rounds()
    payload = history.export_json()

    assert loaded[0].agents[0].answer_rank == 1
    assert loaded[0].agents[0].latency_seconds == 0.3125
    assert loaded[0].agents[1].answer_rank is None
    assert loaded[0].agents[1].latency_seconds is None
    assert payload["schema_version"] == 1
    assert "școală" in path.read_text(encoding="utf-8")


def test_history_grade_update_preserves_answer_metadata(tmp_path: Path) -> None:
    history = HistoryStore(tmp_path / "history.json")
    history.save_round(make_round())

    history.update_grade("round-1", "gemini", Grade.GOOD, 1)

    agent_record = history.load_rounds()[0].agents[0]
    assert agent_record.grade == Grade.GOOD.value
    assert agent_record.score_after == 1
    assert agent_record.answer_rank == 1
    assert agent_record.latency_seconds == 0.3125
    assert history.load_scores() == {"gemini": 1}


def test_load_scores_uses_latest_saved_score_and_applies_legacy_grades(
    tmp_path: Path,
) -> None:
    history = HistoryStore(tmp_path / "history.json")
    first_round = make_round()
    first_round.agents[0].grade = Grade.GOOD.value
    first_round.agents[0].score_after = 1
    second_round = RoundRecord(
        round_id="round-2",
        question="Încă o întrebare?",
        started_at="2026-10-11T15:01:00+03:00",
        agents=[
            AgentRoundRecord(
                agent_id="gemini",
                state="answered",
                grade=Grade.BAD.value,
            ),
            AgentRoundRecord(
                agent_id="chatgpt",
                state="answered",
                grade=Grade.GOOD.value,
            ),
        ],
    )
    history.save_round(first_round)
    history.save_round(second_round)

    assert history.load_scores() == {"gemini": 0, "chatgpt": 1}


def test_malformed_history_loads_as_empty_and_is_replaceable(
    tmp_path: Path,
) -> None:
    path = tmp_path / "history.json"
    path.write_text(json.dumps({"schema_version": 99, "rounds": []}), encoding="utf-8")
    history = HistoryStore(path)

    assert history.load_rounds() == []
    history.save_round(make_round())
    assert history.load_rounds()[0].round_id == "round-1"
