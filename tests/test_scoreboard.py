"""Tests for scoreboard behavior."""

import pytest

from core.models import Agent, Grade
from core.scoreboard import Scoreboard


def make_agent(agent_id: str, score: int = 0) -> Agent:
    """Create an agent with the requested initial score."""
    return Agent(
        id=agent_id,
        name=agent_id.title(),
        color=(10, 20, 30),
        score=score,
    )


def test_good_grade_adds_one_point() -> None:
    scoreboard = Scoreboard(["chatgpt"])

    assert scoreboard.add_grade("chatgpt", Grade.GOOD) == 1
    assert scoreboard.get_score("chatgpt") == 1


def test_bad_grade_subtracts_one_point() -> None:
    scoreboard = Scoreboard(["chatgpt"])

    assert scoreboard.add_grade("chatgpt", Grade.BAD) == -1
    assert scoreboard.get_score("chatgpt") == -1


def test_multiple_grades_accumulate() -> None:
    scoreboard = Scoreboard(["chatgpt"])

    scoreboard.add_grade("chatgpt", Grade.GOOD)
    scoreboard.add_grade("chatgpt", Grade.GOOD)
    scoreboard.add_grade("chatgpt", Grade.BAD)

    assert scoreboard.get_score("chatgpt") == 1


def test_unknown_agent_score_raises_key_error() -> None:
    scoreboard = Scoreboard(["chatgpt"])

    with pytest.raises(KeyError):
        scoreboard.get_score("unknown")
    with pytest.raises(KeyError):
        scoreboard.add_grade("unknown", Grade.GOOD)


def test_ranking_is_descending() -> None:
    scoreboard = Scoreboard(["chatgpt", "gemini", "copilot"])
    scoreboard.add_grade("gemini", Grade.GOOD)
    scoreboard.add_grade("gemini", Grade.GOOD)
    scoreboard.add_grade("copilot", Grade.GOOD)

    assert scoreboard.ranking() == [
        ("gemini", 2),
        ("copilot", 1),
        ("chatgpt", 0),
    ]


def test_ranking_ties_follow_configured_order() -> None:
    scoreboard = Scoreboard(["gemini", "chatgpt", "copilot"])

    assert scoreboard.ranking() == [
        ("gemini", 0),
        ("chatgpt", 0),
        ("copilot", 0),
    ]


def test_registered_agent_scores_seed_scoreboard() -> None:
    scoreboard = Scoreboard([make_agent("gemini", score=3), make_agent("chatgpt")])

    assert scoreboard.ranking() == [("gemini", 3), ("chatgpt", 0)]


def test_reset_zeros_scores_and_preserves_registered_ids() -> None:
    scoreboard = Scoreboard(["gemini", "chatgpt"])
    scoreboard.add_grade("gemini", Grade.GOOD)
    scoreboard.add_grade("chatgpt", Grade.BAD)

    scoreboard.reset()

    assert scoreboard.ranking() == [("gemini", 0), ("chatgpt", 0)]
