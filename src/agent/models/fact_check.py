from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Verdict = Literal["verified_true", "possibly_outdated_inaccurate", "unverifiable"]


@dataclass
class Occurrence:
    start: str
    end: str


@dataclass
class Claim:
    text: str
    occurrences: list[Occurrence]


@dataclass
class EvidenceReference:
    title: str
    url: str | None = None


@dataclass
class Verification:
    verdict: Verdict
    rationale: str
    evidence: list[EvidenceReference]


@dataclass
class FactCheck:
    claim: Claim
    verification: Verification | None = None
