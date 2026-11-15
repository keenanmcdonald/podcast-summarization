import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agent.contracts.summarizer.input import SummarizerFeedback, SummarizerInput
from src.agent.contracts.summarizer.output import SummarizerOutput
from src.agent.model import build_model, system_prompt
from src.agent.models.state import GraphState, NotableQuote, ShowNotes
from src.agent.models.transcript import Transcript, timestamp_seconds
from src.agent.reasoning import log_reasoning_summaries
from src.log_context import log_context

logger = logging.getLogger(__name__)


async def generate_show_notes(state: GraphState) -> dict[str, ShowNotes]:
    logger.info("%s stage=show_notes event=start", log_context())
    transcript = state.transcript
    payload = SummarizerInput.model_validate(
        {
            "transcript": {
                "turns": [turn.model_dump(exclude={"section"}) for turn in transcript.turns],
                "title": transcript.title,
                "host": transcript.host,
                "guests": transcript.guests,
            }
        }
    )
    model = build_model("gpt-6-sol", reasoning_effort="low").with_structured_output(
        SummarizerOutput, method="json_schema", include_raw=True
    )
    messages = [
        SystemMessage(content=system_prompt("summarizer")),
        HumanMessage(content=payload.model_dump_json()),
    ]
    result = await model.ainvoke(messages)
    raw = result["raw"]
    if not isinstance(raw, AIMessage):
        raise TypeError("Summarizer did not return a model message")
    log_reasoning_summaries(raw, logger, "show_notes")
    if result["parsing_error"] is not None:
        raise result["parsing_error"]
    response = result["parsed"]
    if not isinstance(response, SummarizerOutput):
        raise TypeError("Summarizer did not return structured notes")
    errors = validate_notes(response, transcript)
    if errors:
        logger.warning("%s stage=show_notes event=correction issues=%d", log_context(), len(errors))
        feedback = SummarizerFeedback(errors=errors)
        result = await model.ainvoke([*messages, raw, HumanMessage(content=feedback.model_dump_json())])
        corrected = result["raw"]
        if not isinstance(corrected, AIMessage):
            raise TypeError("Summarizer did not return a model message")
        log_reasoning_summaries(corrected, logger, "show_notes")
        if result["parsing_error"] is not None:
            raise result["parsing_error"]
        response = result["parsed"]
        if not isinstance(response, SummarizerOutput):
            raise TypeError("Summarizer did not return structured notes")
        errors = validate_notes(response, transcript)
    if errors:
        raise ValueError(f"Invalid show notes after correction: {errors}")
    logger.info(
        "%s stage=show_notes event=completed takeaways=%d quotes=%d topics=%d",
        log_context(), len(response.takeaways), len(response.quotes), len(response.topics),
    )
    return {
        "show_notes": ShowNotes(
            summary=response.summary,
            takeaways=response.takeaways,
            quotes=[NotableQuote(text=q.text, speaker=q.speaker, timestamp=q.timestamp) for q in response.quotes],
            topics=response.topics,
        )
    }


def validate_notes(response: SummarizerOutput, transcript: Transcript) -> list[str]:
    errors = []
    turns = {(timestamp_seconds(turn.timestamp), turn.speaker): turn.text for turn in transcript.turns}
    for quote in response.quotes:
        try:
            text = turns.get((timestamp_seconds(quote.timestamp), quote.speaker))
        except ValueError:
            text = None
        if text is None:
            errors.append(f"No transcript turn for {quote.speaker} at {quote.timestamp}")
        elif not quote.text.strip() or quote.text not in text:
            errors.append(
                f"Quote for {quote.speaker} at {quote.timestamp} must be a verbatim substring of: {text}"
            )
    return errors
