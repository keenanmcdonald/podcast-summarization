import json
import logging

from langchain_core.messages import AIMessage

from src.log_context import log_context


def log_reasoning_summaries(message: AIMessage, logger: logging.Logger, stage: str) -> None:
    if not isinstance(message.content, list):
        return
    for block in message.content:
        if not isinstance(block, dict) or block.get("type") != "reasoning":
            continue
        for summary in block.get("summary", []):
            text = summary.get("text") if isinstance(summary, dict) else None
            if isinstance(text, str) and text:
                logger.info(
                    "%s stage=%s event=reasoning_summary summary=%s",
                    log_context(), stage, json.dumps(text, ensure_ascii=False),
                )
