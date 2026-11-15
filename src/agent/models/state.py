from dataclasses import dataclass

from src.agent.models.fact_check_state import FactCheckState


@dataclass
class NotableQuote:
    text: str
    speaker: str
    timestamp: str


@dataclass
class ShowNotes:
    summary: str
    takeaways: list[str]
    quotes: list[NotableQuote]
    topics: list[str]


@dataclass
class GraphState(FactCheckState):
    show_notes: ShowNotes | None = None
