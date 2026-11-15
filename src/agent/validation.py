import json
from collections.abc import Sequence
from urllib.parse import urlsplit, urlunsplit

from langchain_core.messages import BaseMessage, ToolMessage

from src.models.report import Report
from src.models.transcript import Transcript, timestamp_seconds


def validate_report(report: Report, transcript: Transcript, messages: Sequence[BaseMessage]) -> list[str]:
    errors = []
    turns = {(timestamp_seconds(turn.timestamp), turn.speaker): turn.text for turn in transcript.turns}
    for quote in report.quotes:
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

    sources = collect_sources(messages)
    for index, check in enumerate(report.fact_checks, start=1):
        for span in check.claim.occurrences:
            try:
                transcript.resolve_span(span.start, span.end)
            except ValueError as error:
                errors.append(f"Claim {index}: {error}")
        verification = check.verification
        if verification.verdict != "unverifiable" and not verification.evidence:
            errors.append(f"Claim {index}: A supported verdict requires cited search evidence")
        for source in verification.evidence:
            search_url = source.url
            if search_url not in sources:
                parts = urlsplit(search_url)
                netloc = (
                    parts.netloc.removeprefix("www.")
                    if parts.netloc.startswith("www.")
                    else f"www.{parts.netloc}"
                )
                search_url = urlunsplit(parts._replace(netloc=netloc))
            if search_url not in sources:
                errors.append(f"Claim {index}: Verdict cites an unknown search result: {source.url}")
            elif source.title != sources[search_url]:
                errors.append(f"Claim {index}: Source title for {source.url} must be: {sources[search_url]}")
    return errors


def collect_sources(messages: Sequence[BaseMessage]) -> dict[str, str]:
    sources = {}
    for message in messages:
        if isinstance(message, ToolMessage) and message.name == "tavily_search" and message.status != "error":
            response = json.loads(message.content)
            for item in response["results"]:
                sources[item["url"]] = item["title"]
    return sources
