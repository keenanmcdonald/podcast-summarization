import unittest
from pathlib import Path
from unittest.mock import patch

from billiard.exceptions import SoftTimeLimitExceeded

from src.log_context import task_id
from src.models.report import Report
from src.models.transcript import Transcript
from src.tasks import TASK_HARD_LIMIT_SECONDS, TASK_SOFT_LIMIT_SECONDS, analyze_episode


class AnalyzeEpisodeTests(unittest.TestCase):
    def test_sequential_tasks_save_reports_without_leaking_task_context(self) -> None:
        observed_task_ids = []
        report = Report(summary="Summary", takeaways=["a", "b", "c", "d", "e"], quotes=[], topics=[], fact_checks=[])

        def analyze_transcript(transcript: Transcript) -> Report:
            observed_task_ids.append(task_id.get())
            return report

        with (
            patch("src.tasks.analyze_transcript", side_effect=analyze_transcript),
            patch("src.tasks.write_report", return_value=Path("mock/demo/ep001/report.json")) as write_report,
            self.assertLogs("src.tasks", level="INFO") as logs,
        ):
            for identifier in ("first-task", "second-task"):
                analyze_episode.push_request(id=identifier)
                try:
                    analyze_episode.run("demo/ep001/transcript.json")
                finally:
                    analyze_episode.pop_request()
                self.assertIsNone(task_id.get())

        self.assertEqual(observed_task_ids, ["first-task", "second-task"])
        self.assertEqual(sum("stage=task event=completed" in line for line in logs.output), 2)
        self.assertTrue(any("stage=transcript event=loaded" in line for line in logs.output))
        self.assertTrue(any("stage=report event=written" in line for line in logs.output))
        self.assertEqual(write_report.call_count, 2)
        self.assertTrue(all(call.args[1] is report for call in write_report.call_args_list))

    def test_failed_task_logs_and_reraises_without_writing_report(self) -> None:
        with (
            patch("src.tasks.resolve_transcript", side_effect=ValueError("bad path")),
            patch("src.tasks.write_report") as write_report,
            self.assertLogs("src.tasks", level="ERROR") as logs,
            self.assertRaisesRegex(ValueError, "bad path"),
        ):
            analyze_episode.run("../bad.json")

        self.assertIn("stage=task event=failed", logs.output[0])
        self.assertIsNone(task_id.get())
        write_report.assert_not_called()

    def test_soft_time_limit_propagates_without_writing_report(self) -> None:
        with (
            patch("src.tasks.analyze_transcript", side_effect=SoftTimeLimitExceeded()),
            patch("src.tasks.write_report") as write_report,
            self.assertLogs("src.tasks", level="ERROR"),
            self.assertRaises(SoftTimeLimitExceeded),
        ):
            analyze_episode.run("demo/ep001/transcript.json")

        self.assertIsNone(task_id.get())
        write_report.assert_not_called()
        self.assertEqual(analyze_episode.soft_time_limit, TASK_SOFT_LIMIT_SECONDS)
        self.assertEqual(analyze_episode.time_limit, TASK_HARD_LIMIT_SECONDS)
