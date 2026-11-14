from dataclasses import dataclass, field
from typing import Literal

from langchain_core.messages import BaseMessage

from src.agent.models.fact_check import FactCheck
from src.agent.models.transcript import Transcript


@dataclass
class VerificationContext:
    messages: list[BaseMessage] = field(default_factory=list)
    evidence: list[object] = field(default_factory=list)


@dataclass
class VerificationProgress:
    search_count: int = 0
    model_turn_count: int = 0
    next_step: Literal["search", "finish"] | None = None


@dataclass
class VerificationState:
    fact_check: FactCheck
    transcript: Transcript
    context: VerificationContext = field(default_factory=VerificationContext)
    progress: VerificationProgress = field(default_factory=VerificationProgress)
