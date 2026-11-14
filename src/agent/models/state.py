import operator
from dataclasses import dataclass, field
from typing import Annotated

from src.agent.models.fact_check import FactCheck
from src.agent.models.show_notes import ShowNotes
from src.agent.models.transcript import Transcript


@dataclass
class GraphState:
    transcript: Transcript
    pending_checks: list[FactCheck] = field(default_factory=list)
    fact_checks: Annotated[list[FactCheck], operator.add] = field(default_factory=list)
    show_notes: ShowNotes | None = None
