import asyncio
import json
import logging
from urllib.parse import urlsplit, urlunsplit

from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    ToolCallLimitMiddleware,
)
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from src.agent.contracts.verifier.input import VerifierInput
from src.agent.contracts.verifier.output import VerifierOutput
from src.agent.model import build_model, system_prompt
from src.agent.search import build_search_tool
from src.agent.reasoning import log_reasoning_summaries
from src.log_context import log_context
from src.agent.models.fact_check import EvidenceReference, FactCheck, Verification
from src.agent.models.transcript import Transcript

MAX_SEARCHES = 3
MAX_MODEL_CALLS = 8
CLAIM_DEADLINE_SECONDS = 180
logger = logging.getLogger(__name__)


def build_verifier() -> CompiledStateGraph:
    search = build_search_tool()
    return create_agent(
        model=build_model("gpt-6-luna", reasoning_effort="medium"),
        tools=[search],
        system_prompt=system_prompt("verifier"),
        response_format=VerifierOutput,
        middleware=[
            ToolCallLimitMiddleware(tool_name=search.name, run_limit=MAX_SEARCHES),
            ModelCallLimitMiddleware(run_limit=MAX_MODEL_CALLS, exit_behavior="error"),
        ],
    )


async def verify_one(
    check: FactCheck, transcript: Transcript, agent: CompiledStateGraph, config: RunnableConfig
) -> FactCheck:
    logger.info("%s stage=claim_verification event=start", log_context())
    payload = VerifierInput.model_validate({
        "claim": {
            "text": check.claim.text,
            "occurrences": [vars(occurrence) for occurrence in check.claim.occurrences],
        },
        "transcript": {
            "turns": [
                turn.model_dump(exclude={"section"})
                for occurrence in check.claim.occurrences
                for turn in transcript.resolve_span(occurrence.start, occurrence.end)
            ],
            "title": transcript.title,
            "host": transcript.host,
            "guests": transcript.guests,
        },
    })
    messages = [HumanMessage(content=payload.model_dump_json())]
    async with asyncio.timeout(CLAIM_DEADLINE_SECONDS):
        for attempt in range(2):
            result = await agent.ainvoke({"messages": messages}, config=config)
            for message in result["messages"][len(messages):]:
                if isinstance(message, AIMessage):
                    log_reasoning_summaries(message, logger, "claim_verification")
            verdict = result["structured_response"]
            if not isinstance(verdict, VerifierOutput):
                raise TypeError("Verifier did not return a structured verdict")
            try:
                sources = resolve_sources(verdict.source_urls, result["messages"])
                if verdict.verdict != "unverifiable" and not sources:
                    raise ValueError("A supported verdict requires cited search evidence")
            except ValueError as error:
                if attempt:
                    raise
                logger.warning("%s stage=claim_verification event=source_correction", log_context())
                messages = [
                    *result["messages"],
                    HumanMessage(
                        content=(
                            f"Source validation failed: {error}. Correct the verdict using only URLs "
                            "returned by the search tool. Do not search again."
                        )
                    ),
                ]
                continue
            logger.info("%s stage=claim_verification event=completed verdict=%s sources=%d", log_context(), verdict.verdict, len(sources))
            return FactCheck(
                claim=check.claim,
                verification=Verification(
                    verdict=verdict.verdict, rationale=verdict.rationale, evidence=sources
                ),
            )
    raise RuntimeError("Verifier did not return a valid verdict")


def resolve_sources(urls: list[str], messages: list[BaseMessage]) -> list[EvidenceReference]:
    results = {}
    for message in messages:
        if isinstance(message, ToolMessage):
            if message.status == "error":
                logger.warning("%s stage=search event=tool_error", log_context())
                continue
            if urls:
                response = json.loads(message.content)
                for item in response["results"]:
                    results[item["url"]] = item["title"]
    sources = []
    for url in urls:
        source_url = url
        if source_url not in results:
            parts = urlsplit(source_url)
            netloc = (
                parts.netloc.removeprefix("www.")
                if parts.netloc.startswith("www.")
                else f"www.{parts.netloc}"
            )
            source_url = urlunsplit(parts._replace(netloc=netloc))
            if source_url not in results:
                raise ValueError(f"Verdict cites an unknown search result: {url}")
        sources.append(EvidenceReference(title=results[source_url], url=source_url))
    return sources
