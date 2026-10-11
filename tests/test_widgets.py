"""Tests for pygame classroom input, buttons, and speech bubbles."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from gui.widgets import Button, QuestionInput, SpeechBubble


def setup_module() -> None:
    pygame.init()
    pygame.display.set_mode((1280, 720))


def teardown_module() -> None:
    pygame.quit()


def test_question_input_submits_on_enter_and_button() -> None:
    font = pygame.font.Font(None, 24)
    question_input = QuestionInput(
        pygame.Rect(20, 20, 300, 40),
        pygame.Rect(330, 20, 120, 40),
        font,
    )
    question_input.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(50, 40))
    )
    for character in "Ce este apa?":
        question_input.handle_event(
            pygame.event.Event(
                pygame.KEYDOWN,
                key=ord(character),
                unicode=character,
            )
        )

    assert question_input.get_text() == "Ce este apa?"
    assert question_input.handle_event(
        pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r")
    )

    assert question_input.get_text() == "Ce este apa?"
    assert question_input.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(350, 40))
    )


def test_question_input_supports_backspace_and_clear() -> None:
    question_input = QuestionInput(
        pygame.Rect(20, 20, 300, 40),
        pygame.Rect(330, 20, 120, 40),
        pygame.font.Font(None, 24),
    )
    question_input.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(50, 40))
    )
    for character in "test":
        question_input.handle_event(
            pygame.event.Event(
                pygame.KEYDOWN,
                key=ord(character),
                unicode=character,
            )
        )
    question_input.handle_event(
        pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE, unicode="")
    )
    assert question_input.get_text() == "tes"
    question_input.clear()
    assert question_input.get_text() == ""


def test_button_only_activates_when_enabled_and_clicked() -> None:
    button = Button(
        pygame.Rect(10, 10, 100, 40),
        "BUN",
        pygame.font.Font(None, 24),
        icon="check",
    )
    click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(20, 20))

    assert button.handle_event(click)
    button.enabled = False
    assert not button.handle_event(click)


def test_speech_bubble_wraps_words_and_long_unbroken_strings() -> None:
    font = pygame.font.Font(None, 20)
    bubble = SpeechBubble(pygame.Rect(10, 10, 120, 100), font)
    text = "Cuvinte pentru împachetare " + "X" * 100
    bubble.set_text(text)
    surface = pygame.Surface((200, 150))

    bubble.draw(surface)

    assert len(bubble._lines) > 2
    assert all(font.size(line)[0] <= bubble.rect.width - 36 for line in bubble._lines)


def test_speech_bubble_scroll_is_clamped() -> None:
    bubble = SpeechBubble(
        pygame.Rect(10, 10, 180, 90),
        pygame.font.Font(None, 20),
    )
    bubble.set_text(" ".join(f"cuvânt{index}" for index in range(100)))

    bubble.scroll(-1000)
    assert bubble._scroll_offset > 0
    maximum = bubble._max_scroll()
    bubble.scroll(-1000)
    assert bubble._scroll_offset == maximum
    bubble.scroll(1000)
    assert bubble._scroll_offset == 0
