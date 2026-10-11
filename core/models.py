"""Framework-independent domain models and state enums."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class AgentState(str, Enum):
    """Possible states of an agent in a classroom round."""

    IDLE = "idle"
    THINKING = "thinking"
    READY = "ready"
    ANSWERED = "answered"
    ERROR = "error"


class Grade(str, Enum):
    """Grades that the teacher can assign to an answer."""

    GOOD = "good"
    BAD = "bad"


@dataclass(frozen=True)
class Answer:
    """Immutable answer returned for one agent in one classroom round."""

    agent_id: str
    question: str
    text: str
    created_at: str
    provider: str
    round_id: str

    def __post_init__(self) -> None:
        """Validate the answer's identity, content, and timestamp."""
        for field_name in ("agent_id", "question", "provider", "round_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string")
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("text must be a non-empty string")
        if not isinstance(self.created_at, str):
            raise TypeError("created_at must be an ISO 8601 timestamp string")
        if "T" not in self.created_at and " " not in self.created_at:
            raise ValueError("created_at must include an ISO 8601 time")
        try:
            datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("created_at must be an ISO 8601 timestamp") from exc


@dataclass
class Agent:
    """Mutable framework-independent state for one classroom student."""

    id: str
    name: str
    color: tuple[int, int, int]
    state: AgentState = AgentState.IDLE
    answer: Answer | None = None
    error_message: str | None = None
    score: int = 0
    graded_round_id: str | None = None

    def __post_init__(self) -> None:
        """Validate the stable identity, RGB color, and initial state."""
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("id must be a non-empty string")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string")
        if (
            not isinstance(self.color, tuple)
            or len(self.color) != 3
            or any(
                not isinstance(channel, int)
                or isinstance(channel, bool)
                or not 0 <= channel <= 255
                for channel in self.color
            )
        ):
            raise ValueError("color must be an RGB tuple with channels from 0 to 255")
        if not isinstance(self.state, AgentState):
            raise TypeError("state must be an AgentState")
        if self.answer is not None and not isinstance(self.answer, Answer):
            raise TypeError("answer must be an Answer or None")
        if self.error_message is not None and not isinstance(self.error_message, str):
            raise TypeError("error_message must be a string or None")
        if not isinstance(self.score, int) or isinstance(self.score, bool):
            raise TypeError("score must be an integer")
        if self.graded_round_id is not None and not isinstance(
            self.graded_round_id, str
        ):
            raise TypeError("graded_round_id must be a string or None")

    def reset_for_round(self) -> None:
        """Clear round-specific data and return the agent to IDLE."""
        self.state = AgentState.IDLE
        self.answer = None
        self.error_message = None
        self.graded_round_id = None

    def set_thinking(self) -> None:
        """Start a new request, clearing data from any previous round."""
        self.state = AgentState.THINKING
        self.answer = None
        self.error_message = None
        self.graded_round_id = None

    def set_ready(self, answer: Answer) -> None:
        """Store a matching answer and transition from THINKING to READY."""
        if self.state is not AgentState.THINKING:
            raise ValueError("only a THINKING agent can become READY")
        if not isinstance(answer, Answer):
            raise TypeError("answer must be an Answer")
        if answer.agent_id != self.id:
            raise ValueError("answer agent_id must match this agent")
        self.answer = answer
        self.error_message = None
        self.state = AgentState.READY

    def set_error(self, message: str) -> None:
        """Record a request failure and transition from THINKING to ERROR."""
        if self.state is not AgentState.THINKING:
            raise ValueError("only a THINKING agent can transition to ERROR")
        if not isinstance(message, str) or not message.strip():
            raise ValueError("message must be a non-empty string")
        self.answer = None
        self.error_message = message
        self.state = AgentState.ERROR
