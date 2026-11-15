import asyncio
import logging
from contextvars import copy_context
from time import monotonic

from celery.signals import worker_process_shutdown

from src.agent.models.transcript import Transcript
from src.celery_app import app
from src.log_context import task_id
from src.service import analyze_transcript
from src.storage import read_transcript, resolve_transcript, write_report

logger = logging.getLogger(__name__)
runner = asyncio.Runner()


@worker_process_shutdown.connect
def close_runner(**kwargs: object) -> None:
    runner.close()


@app.task(bind=True, name="podcast_agent.analyze_episode")
def analyze_episode(self, transcript_path: str) -> None:
    token = task_id.set(self.request.id)
    started = monotonic()
    logger.info("task_id=%s stage=task event=start transcript=%s", self.request.id, transcript_path)
    try:
        path = resolve_transcript(transcript_path)
        contents = read_transcript(path)
        transcript = Transcript.parse(contents, path.suffix.lower())
        logger.info("task_id=%s stage=transcript event=loaded turns=%d", self.request.id, len(transcript.turns))
        report = runner.run(analyze_transcript(transcript), context=copy_context())
        output_path = write_report(path, report)
        logger.info("task_id=%s stage=report event=written path=%s", self.request.id, output_path)
        logger.info("task_id=%s stage=task event=completed duration_s=%.2f", self.request.id, monotonic() - started)
    except Exception:
        logger.exception("task_id=%s stage=task event=failed duration_s=%.2f", self.request.id, monotonic() - started)
        raise
    finally:
        task_id.reset(token)
