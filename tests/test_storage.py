import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.models.report import Report
from src.storage import (
    MAX_TRANSCRIPT_BYTES,
    read_transcript,
    resolve_transcript,
    write_report,
)


class StorageTests(unittest.TestCase):
    def test_resolve_transcript_stays_inside_mock_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch("src.storage.MOCK_ROOT", Path(directory)):
            self.assertEqual(resolve_transcript("episode/transcript.json"), (Path(directory) / "episode/transcript.json").resolve())
            for key in ("../outside.json", "/tmp/outside.json"):
                with self.subTest(key=key), self.assertRaises(ValueError):
                    resolve_transcript(key)

    def test_read_transcript_enforces_format_and_byte_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "transcript.txt"
            path.write_text("hello", encoding="utf-8")
            self.assertEqual(read_transcript(path), "hello")
            with self.assertRaisesRegex(ValueError, "Supported transcript formats"):
                read_transcript(path.with_suffix(".csv"))
            path.write_bytes(b"x" * (MAX_TRANSCRIPT_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "exceeds size limit"):
                read_transcript(path)

    def test_write_report_replaces_report_with_serialized_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            transcript = Path(directory) / "transcript.json"
            target = Path(directory) / "report.json"
            target.write_text("old report")
            report = Report(summary="Summary", takeaways=["One", "Two", "Three", "Four", "Five"], quotes=[], topics=[], fact_checks=[])

            self.assertEqual(write_report(transcript, report), target)
            self.assertEqual(json.loads(target.read_text()), {
                "summary": "Summary", "takeaways": ["One", "Two", "Three", "Four", "Five"], "quotes": [], "topics": [], "fact_checks": []
            })
            self.assertEqual(list(Path(directory).glob(".report-*")), [])
