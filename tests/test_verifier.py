import asyncio
import json
import unittest
from unittest.mock import AsyncMock

from langchain_core.messages import HumanMessage, ToolMessage

from src.agent.contracts.verifier.output import VerifierOutput
from src.agent.models.fact_check import Claim, FactCheck, Occurrence
from src.agent.models.transcript import Transcript, TranscriptTurn
from src.agent.verifier import resolve_sources, verify_one

SEARCH_URL = "https://linkedin.com/in/emily-marie-rogers"
CITED_URL = "https://www.linkedin.com/in/emily-marie-rogers"


def search_result(url: str = SEARCH_URL) -> ToolMessage:
    return ToolMessage(
        content=json.dumps({"results": [{"title": "Emily Rogers", "url": url}]}),
        tool_call_id="search-1",
    )


class ResolveSourcesTests(unittest.TestCase):
    def test_accepts_www_difference_and_returns_original_search_url(self) -> None:
        sources = resolve_sources([CITED_URL], [search_result()])
        self.assertEqual(sources[0].url, SEARCH_URL)
        self.assertEqual(sources[0].title, "Emily Rogers")

    def test_accepts_www_difference_in_either_direction(self) -> None:
        sources = resolve_sources([SEARCH_URL], [search_result(CITED_URL)])
        self.assertEqual(sources[0].url, CITED_URL)

    def test_rejects_different_paths(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown search result"):
            resolve_sources(["https://www.linkedin.com/in/someone-else"], [search_result()])

    def test_rejects_different_schemes_and_queries(self) -> None:
        for url in ("http://www.linkedin.com/in/emily-marie-rogers", f"{CITED_URL}?ref=other"):
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, "unknown search result"):
                resolve_sources([url], [search_result()])


class VerifyOneTests(unittest.TestCase):
    def test_www_difference_needs_no_retry(self) -> None:
        agent = AsyncMock()
        agent.ainvoke.return_value = {
            "structured_response": VerifierOutput(
                verdict="verified_true", rationale="Claim supported", source_urls=[CITED_URL]
            ),
            "messages": [search_result()],
        }
        transcript = Transcript(turns=[TranscriptTurn(timestamp="00:00", speaker="Emily", text="Claim")])
        check = FactCheck(claim=Claim(text="Claim", occurrences=[Occurrence(start="00:00", end="00:00")]))

        result = asyncio.run(verify_one(check, transcript, agent, {}))

        agent.ainvoke.assert_awaited_once()
        self.assertEqual(result.verification.evidence[0].url, SEARCH_URL)

    def test_retries_unknown_source_with_error_feedback(self) -> None:
        search = search_result()
        first = {
            "structured_response": VerifierOutput(
                verdict="unverifiable", rationale="No evidence", source_urls=["https://example.org/other"]
            ),
            "messages": [search],
        }
        corrected = {
            "structured_response": VerifierOutput(
                verdict="unverifiable", rationale="No evidence", source_urls=[]
            ),
            "messages": [search],
        }
        agent = AsyncMock()
        agent.ainvoke.side_effect = [first, corrected]
        transcript = Transcript(turns=[TranscriptTurn(timestamp="00:00", speaker="Emily", text="Claim")])
        check = FactCheck(claim=Claim(text="Claim", occurrences=[Occurrence(start="00:00", end="00:00")]))

        result = asyncio.run(verify_one(check, transcript, agent, {}))

        self.assertEqual(agent.ainvoke.await_count, 2)
        feedback = agent.ainvoke.await_args_list[1].args[0]["messages"][-1]
        self.assertIsInstance(feedback, HumanMessage)
        self.assertIn("https://example.org/other", feedback.content)
        self.assertEqual(result.verification.verdict, "unverifiable")
        self.assertEqual(result.verification.evidence, [])

    def test_stops_after_one_failed_correction(self) -> None:
        invalid = {
            "structured_response": VerifierOutput(
                verdict="verified_true", rationale="Claim supported", source_urls=["https://example.org/other"]
            ),
            "messages": [search_result()],
        }
        agent = AsyncMock()
        agent.ainvoke.return_value = invalid
        transcript = Transcript(turns=[TranscriptTurn(timestamp="00:00", speaker="Emily", text="Claim")])
        check = FactCheck(claim=Claim(text="Claim", occurrences=[Occurrence(start="00:00", end="00:00")]))

        with self.assertRaisesRegex(ValueError, "unknown search result"):
            asyncio.run(verify_one(check, transcript, agent, {}))
        self.assertEqual(agent.ainvoke.await_count, 2)
