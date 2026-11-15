import json
import logging
from collections.abc import Callable
from pathlib import Path

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, ModelResponse, wrap_model_call
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langsmith import traceable

from src.agent.tools.search import search
from src.agent.validation import validate_report
from src.log_context import task_id
from src.models.report import Report
from src.models.transcript import Transcript, timestamp_seconds

MODEL = "gpt-6-sol"
REASONING_EFFORT = "medium"
MAX_MODEL_CALLS = 30
MAX_CORRECTIONS = 1
MODEL_TIMEOUT_SECONDS = 30
PROMPT = Path(__file__).with_name("prompt.md")
logger = logging.getLogger(__name__)


@traceable(name="analyze_transcript")
def analyze_transcript(transcript: Transcript) -> Report:
    model_calls = 0

    @wrap_model_call
    def limit_model_calls(request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]) -> ModelResponse:
        nonlocal model_calls
        if model_calls >= MAX_MODEL_CALLS:
            raise RuntimeError("Episode model call limit exceeded")
        model_calls += 1
        response = handler(request)
        log_reasoning_summaries(response)
        return response

    agent = create_agent(
        model=ChatOpenAI(
            model=MODEL,
            reasoning={"effort": REASONING_EFFORT, "summary": "auto"},
            use_responses_api=True,
            timeout=MODEL_TIMEOUT_SECONDS,
            max_retries=2,
            model_kwargs={"parallel_tool_calls": False},
        ),
        tools=[search],
        system_prompt=PROMPT.read_text(encoding="utf-8"),
        response_format=Report,
        middleware=[limit_model_calls],
    )
    messages = [HumanMessage(content=transcript.model_dump_json(exclude={"turns": {"__all__": {"section"}}}))]
    for attempt in range(MAX_CORRECTIONS + 1):
        result = agent.invoke({"messages": messages}, config={"metadata": {"task_id": task_id.get()}})
        report = result["structured_response"]
        if not isinstance(report, Report):
            raise TypeError("Agent did not return a structured report")
        errors = validate_report(report, transcript, result["messages"])
        if not errors:
            report.fact_checks.sort(key=lambda check: min(
                timestamp_seconds(span.start) for span in check.claim.occurrences
            ))
            return report
        if attempt == MAX_CORRECTIONS:
            raise ValueError(f"Invalid report after correction: {errors}")
        logger.warning("task_id=%s stage=analysis event=correction issues=%d", task_id.get(), len(errors))
        messages = [*result["messages"], HumanMessage(content=json.dumps({"errors": errors}))]
    raise RuntimeError("Agent did not return a valid report")


def log_reasoning_summaries(response: ModelResponse) -> None:
    for message in response.result:
        if not isinstance(message, AIMessage) or not isinstance(message.content, list):
            continue
        for block in message.content:
            if not isinstance(block, dict) or block.get("type") != "reasoning":
                continue
            for item in block.get("summary", []):
                text = item.get("text") if isinstance(item, dict) else None
                if isinstance(text, str) and text:
                    logger.info(
                        "task_id=%s stage=analysis event=reasoning_summary text=%s",
                        task_id.get(), json.dumps(text, ensure_ascii=False),
                    )
