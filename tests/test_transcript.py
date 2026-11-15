import json
import unittest

from pydantic import ValidationError

from src.agent.models.transcript import Transcript, TranscriptTurn


class TranscriptTests(unittest.TestCase):
    def test_parses_text_turns_and_continuations(self) -> None:
        transcript = Transcript.parse("[00:00:01] Host: Hello\ncontinued\n\n[00:00:03] Guest: Yes", ".txt")

        self.assertEqual([(turn.timestamp, turn.speaker, turn.text) for turn in transcript.turns], [
            ("00:00:01", "Host", "Hello continued"), ("00:00:03", "Guest", "Yes")
        ])

    def test_parses_json_metadata_and_turns(self) -> None:
        transcript = Transcript.parse(json.dumps({
            "episode_id": "ep1", "title": "Episode", "host": "Host", "guests": ["Guest"],
            "transcript": [{"timestamp": "00:00", "speaker": "Host", "text": "Hello"}],
        }), ".json")

        self.assertEqual(transcript.episode_id, "ep1")
        self.assertEqual(transcript.guests, ["Guest"])
        self.assertEqual(transcript.turns[0].text, "Hello")

    def test_rejects_unanchored_text_and_unsupported_format(self) -> None:
        with self.assertRaisesRegex(ValueError, "start with a timestamped turn"):
            Transcript.parse("no timestamp", ".txt")
        with self.assertRaisesRegex(ValueError, "Unsupported transcript format"):
            Transcript.parse("anything", ".srt")

    def test_rejects_invalid_turn_order_and_content(self) -> None:
        for turns in (
            [TranscriptTurn(timestamp="00:02", speaker="A", text="One"), TranscriptTurn(timestamp="00:01", speaker="B", text="Two")],
            [TranscriptTurn(timestamp="00:01", speaker="A", text="One"), TranscriptTurn(timestamp="00:01", speaker="B", text="Two")],
            [TranscriptTurn(timestamp="00:01", speaker=" ", text="One")],
            [TranscriptTurn(timestamp="00:61", speaker="A", text="One")],
        ):
            with self.subTest(turns=turns), self.assertRaises(ValidationError):
                Transcript(turns=turns)

    def test_resolves_only_existing_ordered_span_endpoints(self) -> None:
        transcript = Transcript(turns=[
            TranscriptTurn(timestamp="00:01", speaker="A", text="One"),
            TranscriptTurn(timestamp="00:03", speaker="B", text="Two"),
        ])
        self.assertEqual(transcript.resolve_span("00:01", "00:03"), transcript.turns)
        for start, end in (("00:02", "00:03"), ("00:03", "00:01")):
            with self.subTest(start=start, end=end), self.assertRaisesRegex(ValueError, "Unknown or reversed"):
                transcript.resolve_span(start, end)
