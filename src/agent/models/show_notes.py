from dataclasses import dataclass


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
