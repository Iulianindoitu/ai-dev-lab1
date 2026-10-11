"""Application entry point for the static AI Classroom scene."""

from __future__ import annotations

import logging
import os
import sys

import pygame
from dotenv import load_dotenv

from core.classroom import Classroom
from core.history import HistoryStore
from core.models import Agent
from core.scoreboard import Scoreboard
from gui.scene import WINDOW_HEIGHT, WINDOW_WIDTH, ClassroomScene
from providers.base import AgentProviderRouter
from providers.gemini import GeminiProvider
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
        history = HistoryStore(
            os.getenv("AI_CLASSROOM_HISTORY_PATH", "results/history.json")
        )
        saved_scores = history.load_scores()
        for agent in agents:
            agent.score = saved_scores.get(agent.id, 0)
        scoreboard = Scoreboard(agents)
        mock_provider = MockProvider(seed=seed)
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if api_key:
            provider = AgentProviderRouter(
                default_provider=mock_provider,
                agent_providers={
                    "gemini": GeminiProvider(api_key, fallback=mock_provider)
                },
            )
            _LOGGER.info(
                "AI Classroom pornit cu Gemini pentru elevul Gemini și fallback offline."
            )
        else:
            provider = mock_provider
            _LOGGER.info("AI Classroom pornit în modul demo offline.")
        classroom = Classroom(
            agents=agents,
            provider=provider,
            scoreboard=scoreboard,
            history=history,
        )
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
