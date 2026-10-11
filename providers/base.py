"""Shared answer provider abstractions and errors."""

from abc import ABC, abstractmethod

from core.models import Agent


class ProviderError(Exception):
    """Base exception raised when an answer provider cannot answer."""


class ProviderTimeoutError(ProviderError):
    """Raised when an answer provider exceeds its request timeout."""


class AnswerProvider(ABC):
    """Interface implemented by providers that answer classroom questions."""

    @abstractmethod
    def get_answer(self, question: str, agent: Agent) -> str:
        """Return answer text for a question asked on behalf of an agent.

        Implementations must document their timeout behavior and must not
        access GUI frameworks. This method may block until the provider either
        returns or raises a provider error; callers should perform provider
        work away from the GUI thread.
        """
