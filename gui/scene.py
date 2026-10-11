"""Static pygame classroom scene and frame-loop handling."""

from __future__ import annotations

import logging

import pygame

from core.classroom import Classroom
from core.models import AgentState, Grade
from gui.sprites import StudentSprite, TeacherSprite
from gui.widgets import Button, QuestionInput, SpeechBubble

_LOGGER = logging.getLogger(__name__)
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
TARGET_FPS = 60

_WALL = (239, 232, 211)
_FLOOR = (207, 190, 158)
_INK = (39, 48, 55)
_BOARD = (44, 91, 75)
_BOARD_FRAME = (112, 74, 48)
_DESK = (177, 126, 79)
_DESK_EDGE = (113, 75, 46)
_PANEL = (250, 248, 241)
_MUTED = (94, 105, 109)
_AGENT_COLORS: dict[str, tuple[int, int, int]] = {
    "chatgpt": (70, 132, 195),
    "gemini": (219, 157, 52),
    "copilot": (81, 157, 123),
    "grok": (143, 100, 175),
    "claude": (207, 119, 102),
    "deepseek": (67, 165, 174),
}
_DESK_RECTS = (
    pygame.Rect(70, 255, 200, 90),
    pygame.Rect(355, 255, 200, 90),
    pygame.Rect(640, 255, 200, 90),
    pygame.Rect(70, 485, 200, 90),
    pygame.Rect(355, 485, 200, 90),
    pygame.Rect(640, 485, 200, 90),
)
_SCOREBOARD_RECT = pygame.Rect(940, 150, 316, 240)


class ClassroomScene:
    """Draw the static classroom and poll its domain controller each frame."""

    def __init__(
        self,
        classroom: Classroom,
        screen: pygame.Surface,
        clock: pygame.time.Clock,
    ) -> None:
        """Prepare reusable fonts and the static room layout."""
        self.classroom = classroom
        self.screen = screen
        self.clock = clock
        if len(classroom.get_agents()) != len(_DESK_RECTS):
            raise ValueError("the static classroom scene requires exactly six agents")
        self.running = False
        self._shutdown = False
        self._status = "Așteptăm întrebarea profesorului."
        self._font = self._load_font(22)
        self._small_font = self._load_font(17)
        self._title_font = self._load_font(30, bold=True)
        self._panel_font = self._load_font(24, bold=True)
        self._score_font = self._load_font(19)
        self.question_input = QuestionInput(
            pygame.Rect(24, 84, 980, 42),
            pygame.Rect(1020, 84, 236, 42),
            self._font,
            self._small_font,
        )
        self.speech_bubble = SpeechBubble(
            pygame.Rect(940, 400, 316, 260),
            self._small_font,
            title_font=self._score_font,
            footer_height=56,
        )
        self.good_button = Button(
            pygame.Rect(954, 610, 136, 36),
            "BUN",
            self._small_font,
            color=(49, 133, 88),
            icon="check",
        )
        self.bad_button = Button(
            pygame.Rect(1102, 610, 136, 36),
            "RĂU",
            self._small_font,
            color=(173, 68, 58),
            icon="cross",
        )
        self.scoreboard_rect = pygame.Rect(_SCOREBOARD_RECT)
        self._selected_agent_id: str | None = None
        self._student_sprites = {
            agent.id: StudentSprite(
                agent,
                _DESK_RECTS[index],
                self._small_font,
                self._small_font,
            )
            for index, agent in enumerate(classroom.get_agents())
        }
        self._teacher_sprite = TeacherSprite((875, 612), self._small_font)
        self._last_agent_states = {
            agent.id: agent.state for agent in classroom.get_agents()
        }

    @staticmethod
    def _load_font(size: int, bold: bool = False) -> pygame.font.Font:
        """Choose an installed system font with Romanian character support."""
        candidates = ("arial", "segoeui", "dejavusans", "notosans")
        for name in candidates:
            font_path = pygame.font.match_font(name, bold=bold)
            if font_path is not None:
                return pygame.font.Font(font_path, size)
        return pygame.font.Font(None, size)

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle question, student selection, grading, and window events."""
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.running = False
        if self.question_input.handle_event(event):
            self.request_new_round()
        if self.speech_bubble.handle_event(event):
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.good_button.handle_event(event):
                self._grade_selected(Grade.GOOD)
                return
            if self.bad_button.handle_event(event):
                self._grade_selected(Grade.BAD)
                return
            if self._selected_agent_id is not None and self.speech_bubble.rect.collidepoint(event.pos):
                return
            for agent_id, sprite in self._student_sprites.items():
                if sprite.hit_test(event.pos):
                    self._select_agent(agent_id)
                    return

    def update(self, dt: float) -> None:
        """Poll provider results without waiting for worker completion."""
        del dt
        try:
            self.classroom.poll()
            self._update_widget_state()
        except Exception:
            _LOGGER.exception("Could not poll classroom results")
            self._status = "A apărut o eroare la actualizarea clasei."

    def draw(self) -> None:
        """Render the blackboard, six desks, students, teacher, and scores."""
        self.screen.fill(_WALL)
        pygame.draw.rect(self.screen, _FLOOR, (0, 642, WINDOW_WIDTH, 78))
        pygame.draw.line(self.screen, (176, 156, 125), (0, 642), (1280, 642), 3)
        self._draw_header()
        self._draw_blackboard()
        self._draw_classroom()
        self._draw_teacher()
        self._draw_scoreboard()
        self.question_input.draw(self.screen)
        self._draw_selected_answer()
        self._draw_status()

    def run(self) -> None:
        """Run the application event loop at the configured target frame rate."""
        self.running = True
        try:
            while self.running:
                dt = self.clock.tick(TARGET_FPS) / 1000.0
                for event in pygame.event.get():
                    self.handle_event(event)
                self.update(dt)
                self.draw()
                pygame.display.flip()
        finally:
            self.shutdown()

    def request_new_round(self, question: str | None = None) -> None:
        """Submit the entered question and clear selection after success."""
        submitted_question = (
            self.question_input.get_text() if question is None else question
        )
        try:
            self.classroom.ask(submitted_question)
        except ValueError:
            self._status = "Introduceți o întrebare înainte de a începe."
            return
        except (TypeError, RuntimeError) as exc:
            _LOGGER.warning("Question could not be submitted: %s", exc)
            self._status = str(exc)
            return
        self.question_input.clear()
        self._selected_agent_id = None
        self.speech_bubble.set_text("")
        self._status = "Elevii se gândesc..."

    def _select_agent(self, agent_id: str) -> None:
        try:
            agent = self.classroom.select(agent_id)
        except (KeyError, ValueError):
            return
        self._selected_agent_id = agent.id
        answer_text = agent.answer.text if agent.answer is not None else ""
        self.speech_bubble.set_text(answer_text, title=agent.name)
        self._status = f"{agent.name} a răspuns. Alegeți «Bun» sau «Rău»."
        self._update_widget_state()

    def _grade_selected(self, grade: Grade) -> None:
        if self._selected_agent_id is None:
            return
        agent = self.classroom.get_selected_agent()
        if agent is None:
            return
        try:
            self.classroom.grade(self._selected_agent_id, grade)
        except (KeyError, TypeError, ValueError) as exc:
            self._status = str(exc)
            self._update_widget_state()
            return
        label = "Bun" if grade is Grade.GOOD else "Rău"
        delta = "+1" if grade is Grade.GOOD else "-1"
        self._status = f"Răspunsul lui {agent.name} a fost evaluat: {label} ({delta})."
        self._update_widget_state()

    def _update_widget_state(self) -> None:
        selected = self.classroom.get_selected_agent()
        is_ready = selected is not None and selected.state is AgentState.READY
        self.good_button.enabled = is_ready
        self.bad_button.enabled = is_ready
        for agent in self.classroom.get_agents():
            previous_state = self._last_agent_states.get(agent.id)
            if agent.state is not previous_state:
                if agent.state is AgentState.READY:
                    self._status = f"{agent.name} este gata să răspundă."
                elif agent.state is AgentState.ERROR:
                    self._status = agent.error_message or f"Eroare la elevul {agent.name}."
                self._last_agent_states[agent.id] = agent.state

    def _draw_selected_answer(self) -> None:
        self.speech_bubble.draw(self.screen)
        if not self.speech_bubble.visible:
            return
        self.good_button.draw(self.screen)
        self.bad_button.draw(self.screen)

    def shutdown(self) -> None:
        """Release classroom worker resources and pygame on application exit."""
        if self._shutdown:
            return
        self._shutdown = True
        self.classroom.close()
        pygame.quit()

    def _draw_header(self) -> None:
        pygame.draw.rect(self.screen, (250, 248, 241), (0, 0, 1280, 70))
        pygame.draw.line(self.screen, (218, 212, 198), (0, 69), (1280, 69), 2)
        title = self._title_font.render(
            "AI Classroom — Clasa asistenților", True, _INK
        )
        subtitle = self._small_font.render(
            "Învățăm împreună, răspuns după răspuns", True, _MUTED
        )
        self.screen.blit(title, (24, 7))
        self.screen.blit(subtitle, (26, 43))

    def _draw_blackboard(self) -> None:
        frame = pygame.Rect(280, 150, 90, 62)
        pygame.draw.rect(self.screen, _BOARD_FRAME, frame, border_radius=9)
        board = frame.inflate(-14, -14)
        pygame.draw.rect(self.screen, _BOARD, board, border_radius=5)
        message = self._small_font.render("AI", True, (245, 241, 218))
        message_rect = message.get_rect(center=board.center)
        self.screen.blit(message, message_rect)
        pygame.draw.line(
            self.screen,
            (224, 207, 167),
            (frame.left + 35, frame.bottom - 3),
            (frame.right - 35, frame.bottom - 3),
            3,
        )

    def _draw_classroom(self) -> None:
        agents = self.classroom.get_agents()
        for index, desk_rect in enumerate(_DESK_RECTS):
            self._draw_desk(desk_rect)
            self._student_sprites[agents[index].id].draw(self.screen)

    def _draw_desk(self, rect: pygame.Rect) -> None:
        pygame.draw.rect(self.screen, _DESK_EDGE, rect, border_radius=8)
        top = rect.inflate(-5, -7)
        pygame.draw.rect(self.screen, _DESK, top, border_radius=6)
        pygame.draw.line(
            self.screen,
            (218, 173, 119),
            (top.left + 12, top.top + 12),
            (top.right - 12, top.top + 12),
            2,
        )
        leg_y = rect.bottom - 1
        pygame.draw.line(
            self.screen, _DESK_EDGE, (rect.left + 20, leg_y), (rect.left + 25, leg_y + 28), 6
        )
        pygame.draw.line(
            self.screen, _DESK_EDGE, (rect.right - 20, leg_y), (rect.right - 25, leg_y + 28), 6
        )

    def _draw_teacher(self) -> None:
        self._teacher_sprite.draw(self.screen)

    def _draw_scoreboard(self) -> None:
        panel = self.scoreboard_rect
        pygame.draw.rect(self.screen, _PANEL, panel, border_radius=14)
        pygame.draw.rect(self.screen, (210, 205, 191), panel, width=2, border_radius=14)
        heading = self._panel_font.render("CLASAMENT", True, _INK)
        self.screen.blit(heading, (panel.x + 22, panel.y + 20))
        pygame.draw.line(
            self.screen,
            (223, 218, 205),
            (panel.x + 20, panel.y + 60),
            (panel.right - 20, panel.y + 60),
            2,
        )

        agents_by_id = {agent.id: agent for agent in self.classroom.get_agents()}
        rows = self.classroom.get_scoreboard().ranking()
        for position, (agent_id, score) in enumerate(rows, start=1):
            y = panel.y + 64 + (position - 1) * 25
            agent = agents_by_id.get(agent_id)
            name = agent.name if agent is not None else agent_id
            swatch_color = (
                _AGENT_COLORS.get(agent.id, agent.color) if agent is not None else _MUTED
            )
            pygame.draw.circle(self.screen, swatch_color, (panel.x + 32, y + 13), 7)
            rank = self._score_font.render(f"{position}.", True, _MUTED)
            name_image = self._score_font.render(name, True, _INK)
            score_image = self._score_font.render(str(score), True, _INK)
            self.screen.blit(rank, (panel.x + 49, y))
            self.screen.blit(name_image, (panel.x + 80, y))
            self.screen.blit(
                score_image, score_image.get_rect(topright=(panel.right - 22, y))
            )

    def _draw_status(self) -> None:
        status = self._font.render(self._status, True, _INK)
        self.screen.blit(status, (24, 670))
