import logging
import unittest

from langchain_core.messages import AIMessage

from src.agent.model import build_model
from src.agent.reasoning import log_reasoning_summaries


class ReasoningTests(unittest.TestCase):
    def test_requests_openai_reasoning_summaries(self) -> None:
        model = build_model("gpt-6-luna", reasoning_effort="medium")
        self.assertEqual(model.reasoning, {"effort": "medium", "summary": "auto"})
        self.assertTrue(model.use_responses_api)

    def test_logs_only_returned_summary_text(self) -> None:
        message = AIMessage(content=[
            {
                "type": "reasoning",
                "summary": [{"type": "summary_text", "text": "Compare sources.\nCheck dates."}],
                "encrypted_content": "not-for-logs",
            },
            {"type": "text", "text": "Final answer"},
        ])
        logger = logging.getLogger("test.reasoning")

        with self.assertLogs(logger, level="INFO") as logs:
            log_reasoning_summaries(message, logger, "claim_verification")

        self.assertEqual(len(logs.output), 1)
        self.assertIn('summary="Compare sources.\\nCheck dates."', logs.output[0])
        self.assertNotIn("not-for-logs", logs.output[0])
        self.assertNotIn("Final answer", logs.output[0])

    def test_skips_missing_summaries(self) -> None:
        logger = logging.getLogger("test.reasoning")
        with self.assertNoLogs(logger, level="INFO"):
            log_reasoning_summaries(
                AIMessage(content=[{"type": "reasoning", "summary": [], "encrypted_content": "private"}]),
                logger,
                "show_notes",
            )
