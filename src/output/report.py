from dataclasses import dataclass
from typing import Literal


@dataclass
class Quote:
    text: str
    speaker: str
    timestamp: str


@dataclass
class EvidenceReference:
    title: str
    url: str | None = None


@dataclass
class FactCheckRow:
    claim: str
    verdict: Literal["verified_true", "possibly_outdated_inaccurate", "unverifiable"]
    rationale: str
    evidence: list[EvidenceReference]


@dataclass
class Report:
    summary: str
    takeaways: list[str]
    quotes: list[Quote]
    topics: list[str]
    fact_checks: list[FactCheckRow]
