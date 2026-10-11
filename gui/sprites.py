"""Pygame sprites for classroom students and the teacher."""

from __future__ import annotations

import pygame

from core.models import Agent, AgentState

_INK = (39, 48, 55)
_PANEL = (250, 248, 241)
_RANK_COLORS = {
    1: (211, 164, 45),
    2: (133, 143, 153),
    3: (173, 111, 72),
}
_AGENT_COLORS: dict[str, tuple[int, int, int]] = {
    "chatgpt": (70, 132, 195),
    "gemini": (219, 157, 52),
    "copilot": (81, 157, 123),
    "grok": (143, 100, 175),
    "claude": (207, 119, 102),
    "deepseek": (67, 165, 174),
}
_STATE_LABELS: dict[AgentState, tuple[str, tuple[int, int, int]]] = {
    AgentState.IDLE: ("GATA", (87, 107, 96)),
    AgentState.THINKING: ("GÂNDEȘTE…", (43, 104, 142)),
    AgentState.READY: ("GATA SĂ RĂSPUNDĂ", (34, 126, 82)),
    AgentState.ANSWERED: ("EVALUAT", (83, 99, 115)),
    AgentState.ERROR: ("EROARE", (173, 54, 48)),
}


class StudentSprite:
    """Draw a colored student with status above and name below the desk."""

    def __init__(
        self,
        agent: Agent,
        desk_rect: pygame.Rect,
        font: pygame.font.Font,
        status_font: pygame.font.Font | None = None,
    ) -> None:
        """Bind an agent to its desk and text styles."""
        self.agent = agent
        self.desk_rect = pygame.Rect(desk_rect)
        self.font = font
        self.status_font = status_font or font

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the seated student and non-overlapping labels."""
        desk = self.desk_rect
        center_x = desk.centerx
        head_center = (center_x, desk.top - 48)
        color = _AGENT_COLORS.get(self.agent.id, self.agent.color)
        skin = (239, 198, 158)

        pygame.draw.circle(surface, (72, 65, 60), (center_x, head_center[1] + 2), 23)
        pygame.draw.circle(surface, skin, head_center, 20)
        pygame.draw.circle(surface, color, (center_x, desk.top - 11), 18)
        pygame.draw.rect(
            surface,
            color,
            (center_x - 24, desk.top - 4, 48, 24),
            border_radius=8,
        )
        pygame.draw.line(
            surface, skin, (center_x - 18, desk.top + 4), (center_x - 28, desk.top + 17), 6
        )
        pygame.draw.line(
            surface, skin, (center_x + 18, desk.top + 4), (center_x + 28, desk.top + 17), 6
        )

        if (
            self.agent.answer_rank is not None
            and self.agent.state in (AgentState.READY, AgentState.ANSWERED)
        ):
            badge_color = _RANK_COLORS.get(self.agent.answer_rank, (94, 105, 109))
            badge = self.status_font.render(
                f"#{self.agent.answer_rank}", True, (255, 255, 255)
            )
            badge_rect = badge.get_rect(
                center=(center_x, head_center[1] - 31)
            ).inflate(14, 8)
            pygame.draw.rect(surface, badge_color, badge_rect, border_radius=9)
            surface.blit(badge, badge.get_rect(center=badge_rect.center))
        elif self.agent.state is not AgentState.THINKING:
            state_text, state_color = _STATE_LABELS[self.agent.state]
            status = self.status_font.render(state_text, True, state_color)
            status_rect = status.get_rect(midbottom=(center_x, head_center[1] - 25))
            surface.blit(status, status_rect)

        tag_width = min(
            desk.width - 12,
            max(84, self.font.size(self.agent.name)[0] + 20),
        )
        name_tag = pygame.Rect(0, 0, tag_width, 25)
        name_tag.midtop = (center_x, desk.bottom + 5)
        pygame.draw.rect(surface, _PANEL, name_tag, border_radius=6)
        pygame.draw.rect(surface, color, name_tag, width=2, border_radius=6)
        name_surface = self.font.render(self.agent.name, True, _INK)
        surface.blit(name_surface, name_surface.get_rect(center=name_tag.center))

    def hit_test(self, position: tuple[int, int]) -> bool:
        """Return whether a point targets the desk or the visible student."""
        hit_area = self.desk_rect.union(
            pygame.Rect(
                self.desk_rect.left,
                self.desk_rect.top - 90,
                self.desk_rect.width,
                self.desk_rect.height + 120,
            )
        )
        return hit_area.collidepoint(position)


class TeacherSprite:
    """Draw a simple static teacher character."""

    def __init__(
        self,
        position: tuple[int, int],
        font: pygame.font.Font,
    ) -> None:
        """Store the teacher's center position and label font."""
        self.position = position
        self.font = font

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the teacher using pygame primitives."""
        x, y = self.position
        pygame.draw.ellipse(surface, (185, 167, 139), (x - 39, y + 19, 78, 14))
        pygame.draw.circle(surface, (227, 185, 145), (x, y - 23), 18)
        pygame.draw.arc(
            surface,
            (67, 49, 39),
            pygame.Rect(x - 18, y - 41, 36, 28),
            0.0,
            3.14,
            7,
        )
        pygame.draw.rect(surface, (63, 91, 137), (x - 20, y - 4, 40, 39), border_radius=10)
        pygame.draw.line(
            surface, (227, 185, 145), (x - 18, y + 2), (x - 35, y + 18), 7
        )
        pygame.draw.line(
            surface, (227, 185, 145), (x + 18, y + 2), (x + 35, y + 18), 7
        )
        pygame.draw.line(
            surface, (48, 52, 65), (x - 9, y + 32), (x - 11, y + 53), 8
        )
        pygame.draw.line(
            surface, (48, 52, 65), (x + 9, y + 32), (x + 11, y + 53), 8
        )
        label = self.font.render("PROFESOR", True, _INK)
        surface.blit(label, label.get_rect(midtop=(x, y + 54)))
