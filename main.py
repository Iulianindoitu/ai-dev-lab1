"""Application entry point for the static AI Classroom scene."""

from __future__ import annotations

import logging
import os
import sys

import pygame
from dotenv import load_dotenv

from core.classroom import Classroom, RoundRecord
from core.models import Agent, Grade
from core.scoreboard import Scoreboard
from gui.scene import WINDOW_HEIGHT, WINDOW_WIDTH, ClassroomScene
from providers.mock import MockProvider

_LOGGER = logging.getLogger(__name__)
_STUDENTS = (
    ("chatgpt", "ChatGPT", (70, 132, 195)),
    ("gemini", "Gemini", (219, 157, 52)),
    ("copilot", "Copilot", (81, 157, 123)),
    ("grok", "Grok", (143, 100, 175)),
    ("claude", "Claude", (207, 119, 102)),
    ("deepseek", "DeepSeek", (67, 165, 174)),
)


class _InMemoryHistory:
    """Keep this static-demo shell compatible with the classroom controller."""

    def __init__(self) -> None:
        self.rounds: dict[str, RoundRecord] = {}

    def save_round(self, round_record: RoundRecord) -> None:
        self.rounds[round_record.round_id] = round_record

    def update_grade(
        self, round_id: str, agent_id: str, grade: Grade, score_after: int
    ) -> None:
        record = self.rounds[round_id]
        for agent_record in record.agents:
            if agent_record.agent_id == agent_id:
                agent_record.state = "answered"
                agent_record.grade = grade.value
                agent_record.score_after = score_after
                return
        raise KeyError(agent_id)


def _create_agents() -> list[Agent]:
    """Build the six students in their documented classroom order."""
    return [
        Agent(id=agent_id, name=name, color=color)
        for agent_id, name, color in _STUDENTS
    ]


def _configure_logging() -> None:
    """Initialize application logging using the optional environment setting."""
    level_name = os.getenv("AI_CLASSROOM_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, None)
    if not isinstance(level, int):
        raise ValueError(f"Nivel de jurnalizare invalid: {level_name}")
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> int:
    """Initialize pygame, construct the classroom, and run at 60 FPS."""
    load_dotenv()
    try:
        _configure_logging()
        seed_value = os.getenv("AI_CLASSROOM_MOCK_SEED")
        seed = int(seed_value) if seed_value else None
    except ValueError:
        _LOGGER.exception("Configurație invalidă pentru aplicație.")
        return 2

    classroom: Classroom | None = None
    try:
        pygame.init()
        pygame.font.init()
        screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("AI Classroom — Clasa asistenților")
        clock = pygame.time.Clock()

        agents = _create_agents()
        scoreboard = Scoreboard(agents)
        classroom = Classroom(
            agents=agents,
            provider=MockProvider(seed=seed),
            scoreboard=scoreboard,
            history=_InMemoryHistory(),
        )
        _LOGGER.info("AI Classroom pornit în modul demo offline.")
        ClassroomScene(classroom, screen, clock).run()
        return 0
    except Exception:
        _LOGGER.exception("Aplicația nu a putut porni sau a întâmpinat o eroare.")
        return 1
    finally:
        if classroom is not None:
            classroom.close()
        pygame.quit()


if __name__ == "__main__":
    sys.exit(main())
