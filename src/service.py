import asyncio
from collections import Counter

from src.agent.graph import build_graph
from src.agent.models.fact_check import FactCheck
from src.agent.models.state import GraphState
from src.agent.models.transcript import Transcript
from src.contracts.report import EvidenceReference, FactCheckRow, Quote, Report

RUN_DEADLINE_SECONDS = 300


async def analyze_transcript(transcript: Transcript) -> Report:
    async with asyncio.timeout(RUN_DEADLINE_SECONDS):
        result = await build_graph().ainvoke(GraphState(transcript=transcript))
    return build_report(GraphState(**result))


def build_report(state: GraphState) -> Report:
    if state.show_notes is None:
        raise ValueError("Show notes are missing")
    if Counter(check_identity(check) for check in state.fact_checks) != Counter(
        check_identity(check) for check in state.pending_checks
    ):
        raise ValueError("Fact checking is incomplete")

    rows = []
    for check in sorted(state.fact_checks, key=first_occurrence):
        if check.verification is None:
            raise ValueError("Fact checking is incomplete")
        rows.append(
            FactCheckRow(
                claim=check.claim.text,
                verdict=check.verification.verdict,
                rationale=check.verification.rationale,
                evidence=[
                    EvidenceReference(title=source.title, url=source.url)
                    for source in check.verification.evidence
                ],
            )
        )

    notes = state.show_notes
    return Report(
        summary=notes.summary,
        takeaways=notes.takeaways,
        quotes=[Quote(text=q.text, speaker=q.speaker, timestamp=q.timestamp) for q in notes.quotes],
        topics=notes.topics,
        fact_checks=rows,
    )


def check_identity(check: FactCheck) -> tuple[str, tuple[tuple[str, str], ...]]:
    return (
        check.claim.text,
        tuple((span.start, span.end) for span in check.claim.occurrences),
    )


def first_occurrence(check: FactCheck) -> int:
    return min(timestamp_seconds(span.start) for span in check.claim.occurrences)


def timestamp_seconds(timestamp: str) -> int:
    seconds = 0
    for part in timestamp.split(":"):
        seconds = seconds * 60 + int(part)
    return seconds
