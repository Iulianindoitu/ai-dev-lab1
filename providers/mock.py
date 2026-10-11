"""Offline mock answer provider for demos and automated tests."""

import math
import random
import time

from core.models import Agent
from providers.base import AnswerProvider

_DEMO_NOTICE = "Răspuns demonstrativ mock; nu este un răspuns generat de AI."
_STYLE_PREFIXES = {
    "chatgpt": "Pe scurt",
    "gemini": "Să privim întrebarea astfel",
    "copilot": "Pas cu pas",
    "grok": "O perspectivă directă",
    "claude": "Cu puțin context",
    "deepseek": "Analizând ideea",
}
_DEMO_ANSWERS = (
    "Ca exemplu, putem descompune subiectul în câteva idei simple.",
    "Un mod util de a privi întrebarea este să observăm relația dintre cauză și efect.",
    "Pentru o explicație clară, să pornim de la definiția conceptului și un exemplu.",
)
_MISLEADING_ANSWERS = (
    "Afirmație intenționat posibil incorectă: toate obiectele din acest domeniu "
    "se comportă exact la fel.",
    "Afirmație intenționat posibil incorectă: răspunsul este întotdeauna opusul "
    "celui intuitiv, indiferent de context.",
    "Afirmație intenționat posibil incorectă: acest fenomen are o singură cauză "
    "și nu admite excepții.",
)


class MockProvider(AnswerProvider):
    """Return varied, explicitly fictional Romanian answers without networking.

    Each instance owns a seeded random generator, so calls made in the same
    order with the same seed and configuration produce the same answers and
    delay choices. ``min_delay`` and ``max_delay`` set the inclusive delay
    range in seconds; use zero for both to disable waiting in tests.

    Calls sleep for the selected delay before returning. Invoke this provider
    in a worker thread so the delay cannot block a GUI event loop.
    """

    def __init__(
        self,
        seed: int | None = None,
        min_delay: float = 1.0,
        max_delay: float = 4.0,
        wrong_answer_probability: float = 0.15,
    ) -> None:
        """Create a mock provider with deterministic-capable random behavior.

        Args:
            seed: Optional seed for this provider's private random generator.
            min_delay: Minimum simulated delay in seconds.
            max_delay: Maximum simulated delay in seconds.
            wrong_answer_probability: Probability of returning a deliberately
                misleading demonstration answer, from 0.0 to 1.0.

        Raises:
            TypeError: If a setting has an unsupported type.
            ValueError: If a setting is outside its supported range.
        """
        if seed is not None and (
            not isinstance(seed, int) or isinstance(seed, bool)
        ):
            raise TypeError("seed must be an integer or None")
        for name, value in (("min_delay", min_delay), ("max_delay", max_delay)):
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise TypeError(f"{name} must be a finite number")
            if not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number")
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
        if min_delay > max_delay:
            raise ValueError("min_delay must be less than or equal to max_delay")
        if not isinstance(wrong_answer_probability, (int, float)) or isinstance(
            wrong_answer_probability, bool
        ):
            raise TypeError("wrong_answer_probability must be a finite number")
        if not math.isfinite(wrong_answer_probability):
            raise ValueError("wrong_answer_probability must be a finite number")
        if not 0 <= wrong_answer_probability <= 1:
            raise ValueError("wrong_answer_probability must be between 0 and 1")

        self._random = random.Random(seed)
        self._min_delay = float(min_delay)
        self._max_delay = float(max_delay)
        self._wrong_answer_probability = float(wrong_answer_probability)

    def get_answer(self, question: str, agent: Agent) -> str:
        """Return mock text for an agent, after its configured simulated delay.

        Args:
            question: Non-empty classroom question.
            agent: Student for whom the answer is being generated.

        Raises:
            TypeError: If the question or agent has the wrong type.
            ValueError: If the question is empty or whitespace-only.
        """
        if not isinstance(question, str):
            raise TypeError("question must be a string")
        if not question.strip():
            raise ValueError("question must not be empty")
        if not isinstance(agent, Agent):
            raise TypeError("agent must be an Agent")

        delay = self._random.uniform(self._min_delay, self._max_delay)
        if delay > 0:
            time.sleep(delay)

        prefix = _STYLE_PREFIXES.get(agent.id, "Ca răspuns demonstrativ")
        if self._random.random() < self._wrong_answer_probability:
            answer = self._random.choice(_MISLEADING_ANSWERS)
        else:
            answer = self._random.choice(_DEMO_ANSWERS)

        return (
            f"{_DEMO_NOTICE} {agent.name}: {prefix}, la întrebarea "
            f"„{question.strip()}”: {answer}"
        )
