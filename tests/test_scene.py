"""Smoke tests for rendering the static pygame classroom scene."""

import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from core.classroom import Classroom, RoundRecord
from core.models import Agent, Grade
from core.scoreboard import Scoreboard
from gui.scene import ClassroomScene, WINDOW_HEIGHT, WINDOW_WIDTH
from providers.mock import MockProvider


class MemoryHistory:
    """In-memory history adapter for the scene smoke test."""

    def __init__(self) -> None:
        self.rounds: dict[str, RoundRecord] = {}

    def save_round(self, round_record: RoundRecord) -> None:
        self.rounds[round_record.round_id] = round_record

    def update_grade(
        self, round_id: str, agent_id: str, grade: Grade, score_after: int
    ) -> None:
        round_record = self.rounds[round_id]
        for agent_record in round_record.agents:
            if agent_record.agent_id == agent_id:
                agent_record.grade = grade.value
                agent_record.score_after = score_after
                return
        raise KeyError(agent_id)


def test_static_scene_draws_classroom_and_scoreboard() -> None:
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    agents = [
        Agent(id="chatgpt", name="ChatGPT", color=(70, 132, 195)),
        Agent(id="gemini", name="Gemini", color=(219, 157, 52)),
        Agent(id="copilot", name="Copilot", color=(81, 157, 123)),
        Agent(id="grok", name="Grok", color=(143, 100, 175)),
        Agent(id="claude", name="Claude", color=(207, 119, 102)),
        Agent(id="deepseek", name="DeepSeek", color=(67, 165, 174)),
    ]
    classroom = Classroom(
        agents,
        MockProvider(min_delay=0, max_delay=0),
        Scoreboard(agents),
        MemoryHistory(),
    )
    scene = ClassroomScene(classroom, screen, pygame.time.Clock())
    try:
        scene.draw()

        assert screen.get_size() == (1280, 720)
        assert screen.get_at((290, 160))[:3] == (44, 91, 75)
        assert screen.get_at((100, 300))[:3] == (177, 126, 79)
        assert screen.get_at((950, 160))[:3] == (250, 248, 241)
        assert scene.question_input.rect.right < scene.question_input.submit_rect.left
        assert scene.question_input.submit_rect.bottom <= scene.scoreboard_rect.top
        assert scene.scoreboard_rect == pygame.Rect(940, 150, 316, 240)
        assert scene.speech_bubble.rect.topleft == (940, 400)
        assert scene.speech_bubble.rect.size == (316, 260)
        assert scene.good_button.label == "BUN"
        assert scene.good_button.icon == "check"
        assert scene.bad_button.label == "RĂU"
        assert scene.bad_button.icon == "cross"
        assert scene.good_button.rect.bottom <= scene.speech_bubble.rect.bottom
        assert scene.bad_button.rect.bottom <= scene.speech_bubble.rect.bottom
        assert [sprite.desk_rect.center for sprite in scene._student_sprites.values()] == [
            (170, 300),
            (455, 300),
            (740, 300),
            (170, 530),
            (455, 530),
            (740, 530),
        ]
    finally:
        scene.shutdown()


def test_widgets_connect_to_classroom_round_selection_and_grading() -> None:
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    agents = [
        Agent(id="chatgpt", name="ChatGPT", color=(70, 132, 195)),
        Agent(id="gemini", name="Gemini", color=(219, 157, 52)),
        Agent(id="copilot", name="Copilot", color=(81, 157, 123)),
        Agent(id="grok", name="Grok", color=(143, 100, 175)),
        Agent(id="claude", name="Claude", color=(207, 119, 102)),
        Agent(id="deepseek", name="DeepSeek", color=(67, 165, 174)),
    ]
    classroom = Classroom(
        agents,
        MockProvider(seed=7, min_delay=0, max_delay=0),
        Scoreboard(agents),
        MemoryHistory(),
    )
    scene = ClassroomScene(classroom, screen, pygame.time.Clock())
    try:
        scene.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(100, 100))
        )
        for character in "Ce este apa?":
            scene.handle_event(
                pygame.event.Event(
                    pygame.KEYDOWN,
                    key=ord(character),
                    unicode=character,
                )
            )
        scene.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r")
        )
        assert classroom.get_round_id() is not None
        assert scene.question_input.get_text() == ""

        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and any(
            agent.state.value == "thinking" for agent in agents
        ):
            scene.update(1 / 60)
            time.sleep(0.002)
        assert all(agent.state.value == "ready" for agent in agents)

        scene.handle_event(
            pygame.event.Event(
                pygame.MOUSEBUTTONDOWN, button=1, pos=(170, 300)
            )
        )
        assert classroom.get_selected_agent() is agents[0]
        assert scene.speech_bubble.visible
        assert scene.good_button.enabled

        selected = classroom.get_selected_agent()
        assert selected is not None
        expected_latency = f"{selected.latency_seconds:.1f}".replace(".", ",")
        assert scene.speech_bubble._title == (
            f"{selected.name} — locul 1 · {expected_latency} s"
        )
        assert scene.speech_bubble._demo
        assert scene._first_answer_name == agents[0].name
        assert scene._teacher_walk.moving
        scene.update(0.35)
        assert scene._teacher_sprite.position != (875, 612)
        scene.draw()

        scene.handle_event(
            pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                button=1,
                pos=scene.good_button.rect.center,
            )
        )

        assert agents[0].score == 1
        assert agents[0].state.value == "answered"
        assert not scene.good_button.enabled
        assert scene._floating_score is not None
        assert scene._floating_score.text == "+1"

        scene.handle_event(
            pygame.event.Event(
                pygame.MOUSEBUTTONDOWN, button=1, pos=(455, 300)
            )
        )
        assert classroom.get_selected_agent() is agents[1]
        assert scene.speech_bubble._title.startswith("Gemini — locul 2 · ")
        assert scene.speech_bubble._demo
        assert scene._first_answer_name == agents[0].name
        assert scene.bad_button.enabled
        scene.handle_event(
            pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                button=1,
                pos=scene.bad_button.rect.center,
            )
        )
        assert agents[1].score == -1
        assert agents[1].state.value == "answered"
        assert scene._floating_score is not None
        assert scene._floating_score.text == "-1"
    finally:
        scene.shutdown()
