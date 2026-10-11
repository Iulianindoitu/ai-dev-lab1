"""Score tracking and ranking for classroom agents."""

from collections.abc import Iterable

from core.models import Agent, Grade


class Scoreboard:
    """Maintain registered agents' scores in a deterministic order."""

    def __init__(self, agents: Iterable[Agent | str] = ()) -> None:
        """Register agents in their configured order with their current scores.

        Args:
            agents: Agent records or stable agent IDs, in ranking tie-break
                order.

        Raises:
            ValueError: If an ID is empty or duplicated.
        """
        self._scores: dict[str, int] = {}
        for agent in agents:
            if isinstance(agent, Agent):
                agent_id = agent.id
                score = agent.score
            elif isinstance(agent, str):
                agent_id = agent
                score = 0
            else:
                raise TypeError("agents must contain Agent instances or string IDs")
            if not agent_id.strip():
                raise ValueError("agent IDs must be non-empty strings")
            if agent_id in self._scores:
                raise ValueError(f"duplicate agent ID: {agent_id}")
            self._scores[agent_id] = score

    def add_grade(self, agent_id: str, grade: Grade) -> int:
        """Apply one grade and return the agent's resulting score.

        Raises:
            KeyError: If ``agent_id`` is not registered.
            TypeError: If ``grade`` is not a :class:`Grade`.
        """
        if not isinstance(grade, Grade):
            raise TypeError("grade must be a Grade")
        score = self._scores[agent_id]
        score += 1 if grade is Grade.GOOD else -1
        self._scores[agent_id] = score
        return score

    def get_score(self, agent_id: str) -> int:
        """Return an agent's score.

        Raises:
            KeyError: If ``agent_id`` is not registered.
        """
        return self._scores[agent_id]

    def ranking(self) -> list[tuple[str, int]]:
        """Return scores descending, preserving configured order for ties."""
        ordered_scores = enumerate(self._scores.items())
        return [
            (agent_id, score)
            for _, (agent_id, score) in sorted(
                ordered_scores,
                key=lambda item: (-item[1][1], item[0], item[1][0]),
            )
        ]

    def reset(self) -> None:
        """Set every registered agent's score to zero."""
        for agent_id in self._scores:
            self._scores[agent_id] = 0
