"""Reusable pygame input, button, and speech-bubble widgets."""

from __future__ import annotations

import pygame

_INK = (39, 48, 55)
_MUTED = (94, 105, 109)
_PANEL = (250, 248, 241)
_BORDER = (205, 201, 187)
_ACCENT = (53, 116, 94)
_DISABLED = (153, 159, 156)


class QuestionInput:
    """Single-line question input with Enter and button submission."""

    def __init__(
        self,
        rect: pygame.Rect,
        submit_rect: pygame.Rect,
        font: pygame.font.Font,
        button_font: pygame.font.Font | None = None,
    ) -> None:
        """Create the question field and its adjacent submit button."""
        self.rect = pygame.Rect(rect)
        self.submit_rect = pygame.Rect(submit_rect)
        self.font = font
        self.button_font = button_font or font
        self._text = ""
        self._focused = False
        self._submit_requested = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Process typing and return True when Enter or the button submits."""
        self._submit_requested = False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._focused = self.rect.collidepoint(event.pos)
            if self.submit_rect.collidepoint(event.pos):
                self._submit_requested = True
        elif event.type == pygame.KEYDOWN and self._focused:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._submit_requested = True
            elif event.key == pygame.K_BACKSPACE:
                self._text = self._text[:-1]
            elif event.key != pygame.K_ESCAPE and event.unicode.isprintable():
                self._text += event.unicode
        return self._submit_requested

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the input field and its Romanian submit button."""
        pygame.draw.rect(surface, _PANEL, self.rect, border_radius=8)
        border = _ACCENT if self._focused else _BORDER
        pygame.draw.rect(surface, border, self.rect, width=2, border_radius=8)
        shown_text = self._text or "Scrie o întrebare pentru elevi…"
        color = _INK if self._text else _MUTED
        text_surface = self.font.render(shown_text, True, color)
        available_width = self.rect.width - 24
        if text_surface.get_width() > available_width:
            shown_text = self._fit_text(shown_text, available_width)
            text_surface = self.font.render(shown_text, True, color)
        surface.blit(
            text_surface,
            text_surface.get_rect(midleft=(self.rect.left + 12, self.rect.centery)),
        )

        pygame.draw.rect(surface, _ACCENT, self.submit_rect, border_radius=8)
        label = self.button_font.render("Întreabă", True, (255, 255, 255))
        surface.blit(label, label.get_rect(center=self.submit_rect.center))

    def get_text(self) -> str:
        """Return the current question text."""
        return self._text

    def clear(self) -> None:
        """Clear the field after a round starts successfully."""
        self._text = ""

    @property
    def focused(self) -> bool:
        """Whether keyboard input is currently directed to this widget."""
        return self._focused

    def _fit_text(self, text: str, width: int) -> str:
        """Trim the visible input prefix until it fits the field."""
        if width <= 0:
            return ""
        original = text
        while text and self.font.size(f"…{text}")[0] > width:
            text = text[1:]
        return f"…{text}" if text != original else text


class Button:
    """Clickable labeled button with an explicit enabled state."""

    def __init__(
        self,
        rect: pygame.Rect,
        label: str,
        font: pygame.font.Font,
        *,
        color: tuple[int, int, int] = _ACCENT,
        text_color: tuple[int, int, int] = (255, 255, 255),
        icon: str | None = None,
    ) -> None:
        """Create a button with fixed geometry and visual colors."""
        if icon not in (None, "check", "cross"):
            raise ValueError("icon must be None, 'check', or 'cross'")
        self.rect = pygame.Rect(rect)
        self.label = label
        self.font = font
        self.color = color
        self.text_color = text_color
        self.icon = icon
        self.enabled = True

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Return True for a left click within an enabled button."""
        return (
            self.enabled
            and event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and self.rect.collidepoint(event.pos)
        )

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the button, dimming it while disabled."""
        color = self.color if self.enabled else _DISABLED
        pygame.draw.rect(surface, color, self.rect, border_radius=8)
        label = self.font.render(self.label, True, self.text_color)
        if self.icon is None:
            surface.blit(label, label.get_rect(center=self.rect.center))
            return

        icon_center = (self.rect.left + 23, self.rect.centery)
        icon_color = self.text_color
        if self.icon == "check":
            pygame.draw.line(
                surface,
                icon_color,
                (icon_center[0] - 7, icon_center[1]),
                (icon_center[0] - 2, icon_center[1] + 5),
                3,
            )
            pygame.draw.line(
                surface,
                icon_color,
                (icon_center[0] - 2, icon_center[1] + 5),
                (icon_center[0] + 8, icon_center[1] - 6),
                3,
            )
        else:
            pygame.draw.line(
                surface,
                icon_color,
                (icon_center[0] - 6, icon_center[1] - 6),
                (icon_center[0] + 6, icon_center[1] + 6),
                3,
            )
            pygame.draw.line(
                surface,
                icon_color,
                (icon_center[0] + 6, icon_center[1] - 6),
                (icon_center[0] - 6, icon_center[1] + 6),
                3,
            )
        label_rect = label.get_rect(
            center=(self.rect.centerx + 8, self.rect.centery)
        )
        surface.blit(label, label_rect)


class SpeechBubble:
    """Word-wrapped, clipped answer panel with vertical mouse-wheel scrolling."""

    def __init__(
        self,
        rect: pygame.Rect,
        font: pygame.font.Font,
        *,
        title_font: pygame.font.Font | None = None,
        background: tuple[int, int, int] = _PANEL,
        footer_height: int = 0,
    ) -> None:
        """Create an initially empty answer panel."""
        if footer_height < 0:
            raise ValueError("footer_height must be non-negative")
        self.rect = pygame.Rect(rect)
        self.font = font
        self.title_font = title_font or font
        self.background = background
        self.footer_height = footer_height
        self._text = ""
        self._title = ""
        self._lines: list[str] = []
        self._scroll_offset = 0
        self._line_height = max(1, font.get_linesize())

    def set_text(self, text: str, title: str = "") -> None:
        """Set answer content, optionally including a speaker heading."""
        if not isinstance(text, str):
            raise TypeError("speech bubble text must be a string")
        if not isinstance(title, str):
            raise TypeError("speech bubble title must be a string")
        self._text = text
        self._title = title
        self._lines = self._wrap_text(text, self.font, self.rect.width - 36)
        self._scroll_offset = 0

    @property
    def visible(self) -> bool:
        """Whether the bubble currently has answer text to display."""
        return bool(self._text)

    def scroll(self, delta: int) -> None:
        """Scroll by text lines, clamping to the available content."""
        if not isinstance(delta, int) or isinstance(delta, bool):
            raise TypeError("scroll delta must be an integer")
        self._scroll_offset = min(
            max(0, self._scroll_offset - delta),
            self._max_scroll(),
        )

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle mouse-wheel scrolling only while the pointer is in the panel."""
        if (
            event.type == pygame.MOUSEWHEEL
            and self.rect.collidepoint(pygame.mouse.get_pos())
        ):
            self.scroll(event.y)
            return True
        if (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button in (4, 5)
            and self.rect.collidepoint(event.pos)
        ):
            self.scroll(1 if event.button == 4 else -1)
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        """Render a rounded answer panel with clipped wrapped text."""
        if not self._text:
            return
        pygame.draw.rect(surface, self.background, self.rect, border_radius=12)
        pygame.draw.rect(surface, _BORDER, self.rect, width=2, border_radius=12)
        title = self._title or "Răspuns"
        heading = self.title_font.render(title, True, _INK)
        surface.blit(heading, (self.rect.left + 16, self.rect.top + 10))

        viewport = pygame.Rect(
            self.rect.left + 16,
            self.rect.top + 43,
            self.rect.width - 32,
            self.rect.height - 55 - self.footer_height,
        )
        old_clip = surface.get_clip()
        surface.set_clip(viewport)
        start = self._scroll_offset
        for line_index, line in enumerate(self._lines[start:]):
            y = viewport.top + line_index * self._line_height
            if y >= viewport.bottom:
                break
            line_surface = self.font.render(line, True, _INK)
            surface.blit(line_surface, (viewport.left, y))
        surface.set_clip(old_clip)

        if self._max_scroll() > 0:
            indicator = self.font.render("↕", True, _MUTED)
            surface.blit(
                indicator,
                indicator.get_rect(bottomright=(self.rect.right - 10, self.rect.bottom - 4)),
            )

    def _max_scroll(self) -> int:
        viewport_height = self.rect.height - 55 - self.footer_height
        visible_lines = max(1, viewport_height // self._line_height)
        return max(0, len(self._lines) - visible_lines)

    @classmethod
    def _wrap_text(
        cls, text: str, font: pygame.font.Font, max_width: int
    ) -> list[str]:
        """Wrap words, splitting oversized tokens character by character."""
        if max_width <= 0:
            return [text] if text else []
        lines: list[str] = []
        for paragraph in text.splitlines() or [""]:
            words = paragraph.split()
            if not words:
                lines.append("")
                continue
            current = ""
            for word in words:
                if font.size(word)[0] > max_width:
                    if current:
                        lines.append(current)
                        current = ""
                    chunks = cls._split_long_word(word, font, max_width)
                    lines.extend(chunks[:-1])
                    current = chunks[-1]
                    continue
                candidate = f"{current} {word}".strip()
                if current and font.size(candidate)[0] > max_width:
                    lines.append(current)
                    current = word
                else:
                    current = candidate
            lines.append(current)
        return lines

    @staticmethod
    def _split_long_word(word: str, font: pygame.font.Font, max_width: int) -> list[str]:
        chunks: list[str] = []
        current = ""
        for char in word:
            if current and font.size(current + char)[0] > max_width:
                chunks.append(current)
                current = char
            else:
                current += char
        if current:
            chunks.append(current)
        return chunks or [""]
