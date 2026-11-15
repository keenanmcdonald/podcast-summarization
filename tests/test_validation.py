import json
import unittest

from langchain_core.messages import AIMessage, ToolMessage
from pydantic import ValidationError

from src.agent.validation import validate_report
from src.models.report import (
    Claim,
    EvidenceReference,
    FactCheck,
    Occurrence,
    Quote,
    Report,
    Verification,
)
from src.models.transcript import Transcript, TranscriptTurn

SOURCE_URL = "https://example.org/result"


def make_report() -> Report:
    return Report(
        summary="Summary", takeaways=["a", "b", "c", "d", "e"], topics=["Topic"],
        quotes=[Quote(text="result is 42", speaker="Host", timestamp="00:01")],
        fact_checks=[FactCheck(
            claim=Claim(text="The result is 42", occurrences=[Occurrence(start="00:01", end="00:01")]),
            verification=Verification(
                verdict="verified_true", rationale="Supported",
                evidence=[EvidenceReference(title="Result", url=SOURCE_URL)],
            ),
        )],
    )


class ReportValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.transcript = Transcript(turns=[TranscriptTurn(timestamp="00:01", speaker="Host", text="The result is 42")])
        self.report = make_report()
        self.search = ToolMessage(
            name="tavily_search", tool_call_id="search-1",
            content=json.dumps({"results": [{"title": "Result", "url": SOURCE_URL, "content": "The result is 42"}]}),
        )

    def test_accepts_valid_report(self) -> None:
        self.assertEqual(validate_report(self.report, self.transcript, [self.search]), [])

    def test_collects_quote_span_and_source_errors_together(self) -> None:
        self.report.quotes[0].text = "Invented quote"
        check = self.report.fact_checks[0]
        check.claim.occurrences[0].start = "00:02"
        check.verification.evidence[0].url = "https://example.org/unknown"

        errors = validate_report(self.report, self.transcript, [self.search])

        self.assertEqual(len(errors), 3)
        self.assertIn("verbatim substring", errors[0])
        self.assertIn("Unknown or reversed transcript span", errors[1])
        self.assertIn("unknown search result", errors[2])

    def test_rejects_missing_speaker_and_invalid_quote_timestamp(self) -> None:
        for quote in (
            Quote(text="result is 42", speaker="Other", timestamp="00:01"),
            Quote(text="result is 42", speaker="Host", timestamp="invalid"),
            Quote(text=" ", speaker="Host", timestamp="00:01"),
        ):
            with self.subTest(quote=quote):
                self.report.quotes = [quote]
                self.assertEqual(len(validate_report(self.report, self.transcript, [self.search])), 1)

    def test_requires_evidence_for_supported_verdicts(self) -> None:
        verification = self.report.fact_checks[0].verification
        verification.evidence = []
        for verdict in ("verified_true", "possibly_outdated_inaccurate"):
            verification.verdict = verdict
            with self.subTest(verdict=verdict):
                errors = validate_report(self.report, self.transcript, [])
                self.assertIn("requires cited search evidence", errors[0])
        verification.verdict = "unverifiable"
        self.assertEqual(validate_report(self.report, self.transcript, []), [])

    def test_allows_www_difference_but_requires_matching_url_and_title(self) -> None:
        source = self.report.fact_checks[0].verification.evidence[0]
        source.url = "https://www.example.org/result"
        self.assertEqual(validate_report(self.report, self.transcript, [self.search]), [])
        source.title = "Invented title"
        self.assertIn("Source title", validate_report(self.report, self.transcript, [self.search])[0])
        source.title = "Result"
        for url in (
            "http://example.org/result", "https://example.org/result?ref=other",
            "https://example.org/other",
        ):
            with self.subTest(url=url):
                source.url = url
                self.assertIn("unknown search result", validate_report(self.report, self.transcript, [self.search])[0])
        source.url = SOURCE_URL
        self.assertEqual(validate_report(self.report, self.transcript, [self.search]), [])
        search_with_www = ToolMessage(
            name="tavily_search", tool_call_id="search-www",
            content=json.dumps({"results": [{"title": "Result", "url": "https://www.example.org/result"}]}),
        )
        self.assertEqual(validate_report(self.report, self.transcript, [search_with_www]), [])

    def test_ignores_error_and_non_search_messages(self) -> None:
        messages = [
            AIMessage(content=self.search.content),
            ToolMessage(content=self.search.content, tool_call_id="other", name="other_tool"),
            ToolMessage(content="Search failed", tool_call_id="failed", name="tavily_search", status="error"),
        ]
        self.assertIn("unknown search result", validate_report(self.report, self.transcript, messages)[0])

    def test_unverifiable_claim_cannot_cite_invented_sources(self) -> None:
        self.report.fact_checks[0].verification.verdict = "unverifiable"
        self.assertIn("unknown search result", validate_report(self.report, self.transcript, [])[0])

    def test_accepts_report_without_claims_or_quotes(self) -> None:
        self.report.fact_checks = []
        self.report.quotes = []
        self.assertEqual(validate_report(self.report, self.transcript, []), [])

    def test_schema_is_strict_for_every_report_object(self) -> None:
        schema = Report.model_json_schema()
        for name, definition in {"Report": schema, **schema["$defs"]}.items():
            with self.subTest(model=name):
                self.assertIs(definition["additionalProperties"], False)
                self.assertEqual(set(definition["required"]), set(definition["properties"]))

    def test_schema_requires_five_takeaways_occurrences_and_completed_verification(self) -> None:
        for field in ("takeaways", "occurrences", "verification"):
            data = self.report.model_dump()
            if field == "takeaways":
                data["takeaways"] = ["Only one"]
            elif field == "occurrences":
                data["fact_checks"][0]["claim"]["occurrences"] = []
            else:
                data["fact_checks"][0]["verification"] = None
            with self.subTest(field=field), self.assertRaises(ValidationError):
                Report.model_validate(data, strict=True)
