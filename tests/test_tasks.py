import asyncio
import unittest
from pathlib import Path
from unittest.mock import patch

from src.log_context import task_id
from src.tasks import analyze_episode


class AnalyzeEpisodeTests(unittest.TestCase):
    def test_sequential_tasks_reuse_event_loop(self) -> None:
        loops = []
        observed_task_ids = []
        report = object()

        async def analyze_transcript(transcript: object) -> object:
            loops.append(asyncio.get_running_loop())
            observed_task_ids.append(task_id.get())
            return report

        with (
            asyncio.Runner() as runner,
            patch("src.tasks.runner", runner),
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

        self.assertEqual(observed_task_ids, ["first-task", "second-task"])
        self.assertEqual(sum("stage=task event=completed" in line for line in logs.output), 2)
        self.assertTrue(any("stage=transcript event=loaded" in line for line in logs.output))
        self.assertTrue(any("stage=report event=written" in line for line in logs.output))
        self.assertIsNone(task_id.get())

        self.assertEqual(len(loops), 2)
        self.assertIs(loops[0], loops[1])
        self.assertEqual(write_report.call_count, 2)
        self.assertTrue(all(call.args[1] is report for call in write_report.call_args_list))

    def test_failed_task_logs_and_reraises(self) -> None:
        with (
            patch("src.tasks.resolve_transcript", side_effect=ValueError("bad path")),
            self.assertLogs("src.tasks", level="ERROR") as logs,
        ):
            with self.assertRaisesRegex(ValueError, "bad path"):
                analyze_episode.run("../bad.json")

        self.assertIn("stage=task event=failed", logs.output[0])
        self.assertIsNone(task_id.get())
