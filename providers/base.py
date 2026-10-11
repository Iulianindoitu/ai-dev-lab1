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


class AgentProviderRouter(AnswerProvider):
    """Route each agent to a provider, using a default for unmapped agents."""

    def __init__(
        self,
        default_provider: AnswerProvider,
        agent_providers: dict[str, AnswerProvider],
    ) -> None:
        """Create a router with a required default and optional overrides."""
        if not isinstance(default_provider, AnswerProvider):
            raise TypeError("default_provider must implement AnswerProvider")
        if not isinstance(agent_providers, dict) or any(
            not isinstance(agent_id, str)
            or not agent_id.strip()
            or not isinstance(provider, AnswerProvider)
            for agent_id, provider in agent_providers.items()
        ):
            raise TypeError("agent_providers must map non-empty IDs to providers")
        self._default_provider = default_provider
        self._agent_providers = dict(agent_providers)

    def get_answer(self, question: str, agent: Agent) -> str:
        """Delegate an answer request according to the agent's stable ID."""
        provider = self.provider_for(agent)
        return provider.get_answer(question, agent)

    def provider_for(self, agent: Agent) -> AnswerProvider:
        """Return the provider configured for an agent."""
        return self._agent_providers.get(agent.id, self._default_provider)

    def provider_name_for(self, agent: Agent) -> str:
        """Return the actual provider identifier for an agent's latest answer."""
        provider = self.provider_for(agent)
        name = getattr(provider, "response_provider_name", None)
        if not isinstance(name, str):
            name = getattr(provider, "name", None)
        if not isinstance(name, str):
            name = type(provider).__name__.lower()
            if name.endswith("provider"):
                name = name[: -len("provider")]
        return name
