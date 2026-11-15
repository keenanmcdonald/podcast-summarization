import unittest

from src.agent.models.fact_check import Claim, EvidenceReference, FactCheck, Occurrence, Verification
from src.agent.models.state import GraphState, NotableQuote, ShowNotes
from src.agent.models.transcript import Transcript, TranscriptTurn
from src.service import build_report


def make_check(text: str, timestamp: str, verified: bool = True) -> FactCheck:
    return FactCheck(
        claim=Claim(text=text, occurrences=[Occurrence(start=timestamp, end=timestamp)]),
        verification=Verification(
            verdict="verified_true", rationale="Supported",
            evidence=[EvidenceReference(title="Source", url="https://example.org")],
        ) if verified else None,
    )


def make_state() -> GraphState:
    return GraphState(
        transcript=Transcript(turns=[TranscriptTurn(timestamp="00:01", speaker="Host", text="Hello")]),
        show_notes=ShowNotes(
            summary="Summary", takeaways=["Takeaway"],
            quotes=[NotableQuote(text="Hello", speaker="Host", timestamp="00:01")], topics=["Topic"],
        ),
    )


class BuildReportTests(unittest.TestCase):
    def test_maps_notes_and_sorts_checks_by_first_occurrence(self) -> None:
        state = make_state()
        early, late = make_check("Early", "00:01"), make_check("Late", "00:03")
        state.pending_checks = [late, early]
        state.fact_checks = [late, early]

        report = build_report(state)

        self.assertEqual(report.summary, "Summary")
        self.assertEqual(report.quotes[0].text, "Hello")
        self.assertEqual([row.claim for row in report.fact_checks], ["Early", "Late"])
        self.assertEqual(report.fact_checks[0].evidence[0].url, "https://example.org")

    def test_rejects_missing_notes_or_missing_verification(self) -> None:
        state = make_state()
        state.show_notes = None
        with self.assertRaisesRegex(ValueError, "Show notes are missing"):
            build_report(state)
        state = make_state()
        check = make_check("Claim", "00:01", verified=False)
        state.pending_checks = [check]
        state.fact_checks = [check]
        with self.assertRaisesRegex(ValueError, "Fact checking is incomplete"):
            build_report(state)

    def test_rejects_missing_or_duplicate_checks_even_with_matching_count(self) -> None:
        state = make_state()
        early, late = make_check("Early", "00:01"), make_check("Late", "00:03")
        state.pending_checks = [early, late]
        state.fact_checks = [early, early]
        with self.assertRaisesRegex(ValueError, "Fact checking is incomplete"):
            build_report(state)
