import asyncio
import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

from langchain_core.messages import AIMessage

from src.agent.contracts.claim_extractor.output import ClaimExtractorOutput
from src.agent.contracts.summarizer.output import SummarizerOutput
from src.agent.models.fact_check_state import FactCheckState
from src.agent.models.state import GraphState
from src.agent.models.transcript import Transcript, TranscriptTurn
from src.agent.nodes.extract_claims import extract_claims
from src.agent.nodes.generate_show_notes import generate_show_notes


def transcript() -> Transcript:
    return Transcript(turns=[TranscriptTurn(timestamp="00:01", speaker="Host", text="The result is 42", section="Intro")])


def model_with_responses(*responses: object) -> tuple[Mock, AsyncMock]:
    structured = AsyncMock()
    structured.ainvoke.side_effect = [
        {"raw": AIMessage(content=response.model_dump_json()), "parsed": response, "parsing_error": None}
        for response in responses
    ]
    model = Mock()
    model.with_structured_output.return_value = structured
    return model, structured


def claim_output(start: str = "00:01") -> ClaimExtractorOutput:
    return ClaimExtractorOutput.model_validate({
        "claims": [{"text": "The result is 42", "occurrences": [{"start": start, "end": start}]}]
    })


def notes_output(quote: str = "result is 42", speaker: str = "Host") -> SummarizerOutput:
    return SummarizerOutput.model_validate({
        "summary": "Summary", "takeaways": ["a", "b", "c", "d", "e"], "topics": ["Topic"],
        "quotes": [{"text": quote, "speaker": speaker, "timestamp": "00:01"}],
    })


class ClaimExtractionTests(unittest.TestCase):
    def test_extracts_claims_with_transcript_spans(self) -> None:
        model, structured = model_with_responses(claim_output())
        with patch("src.agent.nodes.extract_claims.build_model", return_value=model):
            result = asyncio.run(extract_claims(FactCheckState(transcript=transcript())))

        self.assertEqual(result["pending_checks"][0].claim.occurrences[0].start, "00:01")
        payload = json.loads(structured.ainvoke.await_args.args[0][1].content)
        self.assertNotIn("section", payload["transcript"]["turns"][0])

    def test_rejects_invalid_references_after_one_correction(self) -> None:
        model, structured = model_with_responses(claim_output("00:02"), claim_output("00:02"))
        with patch("src.agent.nodes.extract_claims.build_model", return_value=model):
            with self.assertRaisesRegex(ValueError, "Invalid claim references after correction"):
                asyncio.run(extract_claims(FactCheckState(transcript=transcript())))
        self.assertEqual(structured.ainvoke.await_count, 2)
        correction = structured.ainvoke.await_args.args[0]
        self.assertIsInstance(correction[2], AIMessage)
        self.assertEqual(json.loads(correction[2].content), claim_output("00:02").model_dump())
        feedback = json.loads(correction[-1].content)
        self.assertIn("Unknown or reversed transcript span", feedback["errors"][0])


class ShowNotesTests(unittest.TestCase):
    def test_corrects_quote_to_verbatim_transcript_text(self) -> None:
        model, structured = model_with_responses(notes_output("not in transcript"), notes_output())
        with patch("src.agent.nodes.generate_show_notes.build_model", return_value=model):
            result = asyncio.run(generate_show_notes(GraphState(transcript=transcript())))

        self.assertEqual(result["show_notes"].quotes[0].text, "result is 42")
        self.assertEqual(structured.ainvoke.await_count, 2)
        correction = structured.ainvoke.await_args.args[0]
        self.assertIsInstance(correction[2], AIMessage)
        self.assertEqual(json.loads(correction[2].content), notes_output("not in transcript").model_dump())
        feedback = json.loads(correction[-1].content)
        self.assertIn("verbatim substring", feedback["errors"][0])

    def test_rejects_unknown_speaker_after_one_correction(self) -> None:
        model, structured = model_with_responses(notes_output(speaker="Other"), notes_output(speaker="Other"))
        with patch("src.agent.nodes.generate_show_notes.build_model", return_value=model):
            with self.assertRaisesRegex(ValueError, "Invalid show notes after correction"):
                asyncio.run(generate_show_notes(GraphState(transcript=transcript())))
        self.assertEqual(structured.ainvoke.await_count, 2)
