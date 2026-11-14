from src.agent.graph import build_graph
from src.agent.models.fact_check import FactCheck
from src.agent.models.state import GraphState
from src.agent.models.transcript import Transcript
from src.output.report import EvidenceReference, FactCheckRow, Quote, Report


async def analyze_transcript(transcript: Transcript) -> Report:
    result = await build_graph().ainvoke(GraphState(transcript=transcript))
    return build_report(GraphState(**result))


def build_report(state: GraphState) -> Report:
    if state.show_notes is None:
        raise ValueError("Show notes are missing")
    if len(state.fact_checks) != len(state.pending_checks):
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


def first_occurrence(check: FactCheck) -> int:
    return min(timestamp_seconds(span.start) for span in check.claim.occurrences)


def timestamp_seconds(timestamp: str) -> int:
    seconds = 0
    for part in timestamp.split(":"):
        seconds = seconds * 60 + int(part)
    return seconds
