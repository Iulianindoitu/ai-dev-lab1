"""Small time-based pygame animations used by the classroom scene."""

from __future__ import annotations

import math

import pygame

_SKIN = (239, 198, 158)


def _validate_dt(dt: float) -> None:
    if not isinstance(dt, (int, float)) or isinstance(dt, bool):
        raise TypeError("dt must be a finite non-negative number")
    if not math.isfinite(dt) or dt < 0:
        raise ValueError("dt must be a finite non-negative number")


class ThinkingDots:
    """Draw three gently pulsing dots while an agent is thinking."""

    def __init__(self) -> None:
        self.elapsed = 0.0

    def update(self, dt: float) -> None:
        """Advance the repeating dot pulse."""
        _validate_dt(dt)
        self.elapsed += dt

    def draw(
        self,
        surface: pygame.Surface,
        center: tuple[int, int],
        color: tuple[int, int, int] = (43, 104, 142),
    ) -> None:
        """Draw the animated dots centered above the student's head."""
        for index in range(3):
            phase = (self.elapsed * 5.0 - index * 0.8) % (2 * math.pi)
            radius = 3 + round((math.sin(phase) + 1) * 1.5)
            x = center[0] + (index - 1) * 13
            pygame.draw.circle(surface, color, (x, center[1]), radius)


class RaisedHand:
    """Draw a student's raised hand with a subtle bouncing motion."""

    def __init__(self) -> None:
        self.elapsed = 0.0

    def update(self, dt: float) -> None:
        """Advance the hand's bounce phase."""
        _validate_dt(dt)
        self.elapsed += dt

    def draw(
        self,
        surface: pygame.Surface,
        desk_rect: pygame.Rect,
        color: tuple[int, int, int],
        *,
        bouncing: bool = True,
    ) -> None:
        """Draw the raised right arm and hand beside the student's head."""
        desk = pygame.Rect(desk_rect)
        center_x = desk.centerx
        bounce = round(math.sin(self.elapsed * 7.0) * 4) if bouncing else 0
        shoulder = (center_x + 17, desk.top + 5)
        elbow = (center_x + 31, desk.top - 9 + bounce)
        hand = (center_x + 29, desk.top - 42 + bounce)
        pygame.draw.line(surface, color, shoulder, elbow, 8)
        pygame.draw.line(surface, _SKIN, elbow, hand, 7)
        pygame.draw.circle(surface, _SKIN, hand, 6)


class TeacherWalk:
    """Move a teacher between positions using a smooth ease-in/out curve."""

    def __init__(self, position: tuple[float, float]) -> None:
        self.position = (float(position[0]), float(position[1]))
        self._start = self.position
        self._target = self.position
        self._elapsed = 0.0
        self._duration = 0.0

    @property
    def moving(self) -> bool:
        """Whether the current walk has not reached its destination."""
        return self._elapsed < self._duration

    def move_to(
        self, target: tuple[float, float], duration: float = 0.7
    ) -> None:
        """Begin a walk from the current position to a new target."""
        if not isinstance(duration, (int, float)) or isinstance(duration, bool):
            raise TypeError("duration must be a finite positive number")
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("duration must be a finite positive number")
        self._start = self.position
        self._target = (float(target[0]), float(target[1]))
        self._elapsed = 0.0
        self._duration = float(duration)

    def update(self, dt: float) -> tuple[int, int]:
        """Advance the walk and return the rounded screen position."""
        _validate_dt(dt)
        if not self.moving:
            return round(self.position[0]), round(self.position[1])
        self._elapsed = min(self._duration, self._elapsed + dt)
        progress = self._elapsed / self._duration
        eased = progress * progress * (3 - 2 * progress)
        self.position = (
            self._start[0] + (self._target[0] - self._start[0]) * eased,
            self._start[1] + (self._target[1] - self._start[1]) * eased,
        )
        return round(self.position[0]), round(self.position[1])


class FloatingScore:
    """Fade and float a grade's ``+1`` or ``-1`` text above a desk."""

    DURATION = 0.9

    def __init__(
        self,
        position: tuple[int, int],
        delta: int,
        color: tuple[int, int, int],
    ) -> None:
        if delta not in (-1, 1):
            raise ValueError("delta must be -1 or 1")
        self.position = position
        self.text = f"{delta:+d}"
        self.color = color
        self.elapsed = 0.0

    @property
    def active(self) -> bool:
        """Whether the score popup remains visible."""
        return self.elapsed < self.DURATION

    def update(self, dt: float) -> None:
        """Advance the popup's rise and fade."""
        _validate_dt(dt)
        self.elapsed = min(self.DURATION, self.elapsed + dt)

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        """Render the score with decreasing opacity as it floats upward."""
        if not self.active:
            return
        progress = self.elapsed / self.DURATION
        image = font.render(self.text, True, self.color)
        image.set_alpha(round(255 * (1 - progress)))
        rect = image.get_rect(
            center=(self.position[0], round(self.position[1] - progress * 42))
        )
        surface.blit(image, rect)
