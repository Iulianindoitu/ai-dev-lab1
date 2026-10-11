"""Unit tests for classroom animation timing and drawing."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from gui.animations import FloatingScore, RaisedHand, TeacherWalk, ThinkingDots


@pytest.fixture(autouse=True)
def initialize_pygame() -> None:
    pygame.init()


def test_thinking_dots_draw_and_advance() -> None:
    surface = pygame.Surface((100, 100))
    surface.fill((255, 255, 255))
    dots = ThinkingDots()

    dots.draw(surface, (50, 50), (10, 20, 30))
    assert surface.get_at((50, 50))[:3] == (10, 20, 30)
    dots.update(0.25)
    assert dots.elapsed == pytest.approx(0.25)


def test_raised_hand_draws_over_the_student_desk() -> None:
    surface = pygame.Surface((200, 180))
    surface.fill((255, 255, 255))
    hand = RaisedHand()
    desk = pygame.Rect(40, 90, 100, 40)

    hand.draw(surface, desk, (20, 80, 140))

    assert surface.get_at((desk.centerx + 17, desk.top + 5))[:3] == (20, 80, 140)
    hand.update(0.2)
    assert hand.elapsed == pytest.approx(0.2)


def test_teacher_walk_uses_easing_and_reaches_target() -> None:
    walk = TeacherWalk((10, 20))
    walk.move_to((110, 80), duration=1)

    halfway = walk.update(0.5)
    assert halfway == (60, 50)
    assert walk.moving
    assert walk.update(0.5) == (110, 80)
    assert not walk.moving
    assert walk.update(0.1) == (110, 80)


def test_floating_score_rises_then_expires() -> None:
    pygame.font.init()
    surface = pygame.Surface((100, 100))
    score = FloatingScore((50, 80), -1, (173, 68, 58))

    assert score.text == "-1"
    score.update(0.45)
    assert score.active
    score.draw(surface, pygame.font.Font(None, 24))
    assert surface.get_bounding_rect().height > 0
    score.update(0.45)
    assert not score.active


@pytest.mark.parametrize("dt", [-0.1, float("inf"), float("nan")])
def test_animation_rejects_invalid_frame_delta(dt: float) -> None:
    with pytest.raises(ValueError, match="dt"):
        ThinkingDots().update(dt)

