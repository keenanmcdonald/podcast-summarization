from dataclasses import dataclass, field

from src.agent.models.fact_check import FactCheck
from src.agent.models.transcript import Transcript


@dataclass
class FactCheckState:
    transcript: Transcript
    pending_checks: list[FactCheck] = field(default_factory=list)
    fact_checks: list[FactCheck] = field(default_factory=list)
