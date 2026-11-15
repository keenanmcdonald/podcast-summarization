import json
import unittest
from collections.abc import Sequence
from typing import Any, Self
from unittest.mock import patch

from langchain.agents.middleware import ModelResponse
from langchain.agents.structured_output import StructuredOutputValidationError
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from src.agent.run import analyze_transcript, log_reasoning_summaries
from src.models.report import Claim, FactCheck, Occurrence, Quote, Report, Verification
from src.models.transcript import Transcript, TranscriptTurn


class ScriptedModel(BaseChatModel):
    profile: dict[str, bool] = Field(default_factory=lambda: {"structured_output": True})
    responses: list[AIMessage] = Field(default_factory=list)
    received_messages: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Sequence[object], **kwargs: Any) -> Self:
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.received_messages.append(messages)
        return ChatResult(generations=[ChatGeneration(message=self.responses.pop(0))])


def make_report(quote: str = "result is 42") -> Report:
    return Report(
        summary="Summary", takeaways=["a", "b", "c", "d", "e"], topics=["Topic"],
        quotes=[Quote(text=quote, speaker="Host", timestamp="00:01")], fact_checks=[],
    )


def search_request(identifier: str = "search-1") -> AIMessage:
    return AIMessage(content="", tool_calls=[{
        "name": "tavily_search", "args": {"query": "the result"}, "id": identifier, "type": "tool_call",
    }])


class AnalyzeTranscriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = ScriptedModel()
        self.transcript = Transcript(turns=[
            TranscriptTurn(timestamp="00:01", speaker="Host", text="The result is 42", section="Intro"),
            TranscriptTurn(timestamp="00:03", speaker="Guest", text="Another claim"),
        ])
        self.enterContext(patch.dict("os.environ", {"TAVILY_API_KEY": "test-key", "LANGSMITH_TRACING": "false"}))
        self.model_factory = self.enterContext(patch("src.agent.run.ChatOpenAI", return_value=self.model))
        client = self.enterContext(patch("src.agent.tools.search.TavilyClient"))
        self.search = client.return_value.__enter__.return_value.search
        self.search.return_value = {"results": [{
            "title": "Result", "url": "https://example.org/result", "content": "The result is 42",
        }]}

    def test_returns_report_and_sends_transcript_without_section(self) -> None:
        expected = make_report()
        self.model.responses = [AIMessage(content=expected.model_dump_json())]

        result = analyze_transcript(self.transcript)

        self.assertEqual(result, expected)
        messages = self.model.received_messages[0]
        payload = json.loads(next(message.content for message in messages if isinstance(message, HumanMessage)))
        self.assertEqual(payload["turns"][0]["text"], "The result is 42")
        self.assertNotIn("section", payload["turns"][0])
        self.assertEqual(self.model_factory.call_args.kwargs["reasoning"], {"effort": "medium", "summary": "auto"})
        self.assertTrue(self.model_factory.call_args.kwargs["use_responses_api"])
        self.search.assert_not_called()

    def test_corrects_quote_using_existing_conversation(self) -> None:
        invalid = make_report("Invented quote")
        corrected = make_report()
        self.model.responses = [AIMessage(content=report.model_dump_json()) for report in (invalid, corrected)]

        with self.assertLogs("src.agent.run", level="WARNING") as logs:
            result = analyze_transcript(self.transcript)

        self.assertEqual(result, corrected)
        self.assertEqual(len(self.model.received_messages), 2)
        correction_messages = self.model.received_messages[1]
        self.assertTrue(any(isinstance(message, AIMessage) and message.content == invalid.model_dump_json() for message in correction_messages))
        self.assertIn("verbatim substring", correction_messages[-1].content)
        self.assertIn("event=correction", logs.output[0])

    def test_provider_schema_validation_failure_propagates(self) -> None:
        invalid = make_report().model_dump()
        invalid["takeaways"] = ["Only one"]
        self.model.responses = [AIMessage(content=json.dumps(invalid))]

        with self.assertRaisesRegex(StructuredOutputValidationError, "takeaways"):
            analyze_transcript(self.transcript)

        self.assertEqual(len(self.model.received_messages), 1)

    def test_fails_after_one_unsuccessful_correction(self) -> None:
        self.model.responses = [AIMessage(content=make_report("Invented quote").model_dump_json()) for _ in range(3)]

        with (
            self.assertLogs("src.agent.run", level="WARNING"),
            self.assertRaisesRegex(ValueError, "Invalid report after correction"),
        ):
            analyze_transcript(self.transcript)

        self.assertEqual(len(self.model.received_messages), 2)
        self.assertEqual(len(self.model.responses), 1)

    def test_searches_and_preserves_evidence_across_correction(self) -> None:
        report = make_report("Invented quote")
        report.fact_checks = [FactCheck.model_validate({
            "claim": {"text": "The result is 42", "occurrences": [{"start": "00:01", "end": "00:01"}]},
            "verification": {
                "verdict": "verified_true", "rationale": "Supported",
                "evidence": [{"title": "Result", "url": "https://example.org/result"}],
            },
        })]
        invalid = AIMessage(content=report.model_dump_json())
        report.quotes[0].text = "result is 42"
        self.model.responses = [search_request(), invalid, AIMessage(content=report.model_dump_json())]

        with self.assertLogs("src.agent.run", level="WARNING"):
            result = analyze_transcript(self.transcript)

        self.assertEqual(result, report)
        self.search.assert_called_once()
        self.assertTrue(any(isinstance(message, ToolMessage) for message in self.model.received_messages[-1]))

    def test_sorts_checks_by_first_occurrence(self) -> None:
        report = make_report()
        report.fact_checks = [FactCheck(
            claim=Claim(text=text, occurrences=[Occurrence(start=timestamp, end=timestamp)]),
            verification=Verification(verdict="unverifiable", rationale="No usable evidence", evidence=[]),
        ) for text, timestamp in (("Late", "00:03"), ("Early", "00:01"))]
        self.model.responses = [AIMessage(content=report.model_dump_json())]

        result = analyze_transcript(self.transcript)

        self.assertEqual([check.claim.text for check in result.fact_checks], ["Early", "Late"])

    def test_model_budget_does_not_reset_on_correction(self) -> None:
        self.model.responses = [AIMessage(content=make_report("Invented quote").model_dump_json())]

        with (
            patch("src.agent.run.MAX_MODEL_CALLS", 1),
            self.assertLogs("src.agent.run", level="WARNING"),
            self.assertRaisesRegex(RuntimeError, "Episode model call limit exceeded"),
        ):
            analyze_transcript(self.transcript)

        self.assertEqual(len(self.model.received_messages), 1)

    def test_logs_only_provider_reasoning_summaries(self) -> None:
        message = AIMessage(content=[
            {"type": "reasoning", "summary": [{"type": "summary_text", "text": "Check sources.\nCompare dates."}],
             "encrypted_content": "private-content"},
            {"type": "text", "text": "Final answer"},
        ])
        with self.assertLogs("src.agent.run", level="INFO") as logs:
            log_reasoning_summaries(ModelResponse(result=[message]))
        self.assertEqual(len(logs.output), 1)
        self.assertIn('text="Check sources.\\nCompare dates."', logs.output[0])
        self.assertNotIn("private-content", logs.output[0])
        self.assertNotIn("Final answer", logs.output[0])

    def test_budgets_are_fresh_for_each_episode(self) -> None:
        self.model.responses = [AIMessage(content=make_report().model_dump_json()) for _ in range(2)]
        with patch("src.agent.run.MAX_MODEL_CALLS", 1):
            analyze_transcript(self.transcript)
            analyze_transcript(self.transcript)
        self.assertEqual(len(self.model.received_messages), 2)

    def test_search_failure_is_reported_to_agent_without_exposing_provider_error(self) -> None:
        self.search.side_effect = RuntimeError("Provider unavailable")
        self.model.responses = [search_request(), AIMessage(content=make_report().model_dump_json())]

        with self.assertLogs("src.agent.tools.search", level="ERROR"):
            result = analyze_transcript(self.transcript)

        self.assertEqual(result, make_report())
        tool_messages = [message for message in self.model.received_messages[-1] if isinstance(message, ToolMessage)]
        self.assertEqual(len(tool_messages), 1)
        self.assertIn("Web search unavailable", tool_messages[0].content)
        self.assertNotIn("Provider unavailable", tool_messages[0].content)
