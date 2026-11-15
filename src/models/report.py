from typing import Literal

from pydantic import BaseModel, Field


class Quote(BaseModel, extra="forbid"):
    text: str
    speaker: str
    timestamp: str


class Occurrence(BaseModel, extra="forbid"):
    start: str
    end: str


class Claim(BaseModel, extra="forbid"):
    text: str
    occurrences: list[Occurrence] = Field(min_length=1)


class EvidenceReference(BaseModel, extra="forbid"):
    title: str
    url: str


class Verification(BaseModel, extra="forbid"):
    verdict: Literal["verified_true", "possibly_outdated_inaccurate", "unverifiable"]
    rationale: str
    evidence: list[EvidenceReference]


class FactCheck(BaseModel, extra="forbid"):
    claim: Claim
    verification: Verification


class Report(BaseModel, extra="forbid"):
    summary: str = Field(
        description="Approximately 200–300 words covering the episode's core themes, discussions, and outcomes or opinions."
    )
    takeaways: list[str] = Field(min_length=5, max_length=5)
    quotes: list[Quote]
    topics: list[str]
    fact_checks: list[FactCheck]
