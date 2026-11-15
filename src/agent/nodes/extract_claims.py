import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agent.contracts.claim_extractor.input import (
    ClaimExtractorInput,
    ClaimReferenceFeedback,
)
from src.agent.contracts.claim_extractor.output import ClaimExtractorOutput
from src.agent.model import build_model, system_prompt
from src.agent.models.fact_check import Claim, FactCheck, Occurrence
from src.agent.models.fact_check_state import FactCheckState
from src.agent.models.transcript import Transcript
from src.agent.reasoning import log_reasoning_summaries
from src.log_context import log_context

logger = logging.getLogger(__name__)


async def extract_claims(state: FactCheckState) -> dict[str, list[FactCheck]]:
    logger.info("%s stage=claim_extraction event=start", log_context())
    transcript = state.transcript
    payload = ClaimExtractorInput.model_validate({
        "transcript": {
            "turns": [turn.model_dump(exclude={"section"}) for turn in transcript.turns],
            "title": transcript.title,
            "host": transcript.host,
            "guests": transcript.guests,
        }
    })
    model = build_model("gpt-6-sol", reasoning_effort="low").with_structured_output(
        ClaimExtractorOutput, method="json_schema", include_raw=True
    )
    messages = [
        SystemMessage(content=system_prompt("claim_extractor")),
        HumanMessage(content=payload.model_dump_json()),
    ]
    result = await model.ainvoke(messages)
    raw = result["raw"]
    if not isinstance(raw, AIMessage):
        raise TypeError("Claim extractor did not return a model message")
    log_reasoning_summaries(raw, logger, "claim_extraction")
    if result["parsing_error"] is not None:
        raise result["parsing_error"]
    response = result["parsed"]
    if not isinstance(response, ClaimExtractorOutput):
        raise TypeError("Claim extractor did not return structured claims")
    errors = validate_references(response, transcript)
    if errors:
        logger.warning("%s stage=claim_extraction event=correction issues=%d", log_context(), len(errors))
        feedback = ClaimReferenceFeedback(errors=errors)
        result = await model.ainvoke([*messages, raw, HumanMessage(content=feedback.model_dump_json())])
        corrected = result["raw"]
        if not isinstance(corrected, AIMessage):
            raise TypeError("Claim extractor did not return a model message")
        log_reasoning_summaries(corrected, logger, "claim_extraction")
        if result["parsing_error"] is not None:
            raise result["parsing_error"]
        response = result["parsed"]
        if not isinstance(response, ClaimExtractorOutput):
            raise TypeError("Claim extractor did not return structured claims")
        errors = validate_references(response, transcript)
    if errors:
        raise ValueError(f"Invalid claim references after correction: {errors}")
    logger.info("%s stage=claim_extraction event=completed claims=%d", log_context(), len(response.claims))
    return {"pending_checks": [
        FactCheck(claim=Claim(
            text=claim.text,
            occurrences=[Occurrence(start=span.start, end=span.end) for span in claim.occurrences],
        ))
        for claim in response.claims
    ]}


def validate_references(response: ClaimExtractorOutput, transcript: Transcript) -> list[str]:
    errors = []
    for index, claim in enumerate(response.claims):
        for span in claim.occurrences:
            try:
                transcript.resolve_span(span.start, span.end)
            except ValueError as error:
                errors.append(f"Claim {index + 1}: {error}")
    return errors
