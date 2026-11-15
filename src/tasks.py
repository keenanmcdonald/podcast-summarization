import logging
from time import monotonic

from src.agent.run import analyze_transcript
from src.celery_app import app
from src.log_context import task_id
from src.models.transcript import Transcript
from src.storage import read_transcript, resolve_transcript, write_report

TASK_SOFT_LIMIT_SECONDS = 300
TASK_HARD_LIMIT_SECONDS = 330
logger = logging.getLogger(__name__)


@app.task(
    bind=True,
    name="podcast_agent.analyze_episode",
    soft_time_limit=TASK_SOFT_LIMIT_SECONDS,
    time_limit=TASK_HARD_LIMIT_SECONDS,
)
def analyze_episode(self, transcript_path: str) -> None:
    token = task_id.set(self.request.id)
    started = monotonic()
    logger.info("task_id=%s stage=task event=start transcript=%s", self.request.id, transcript_path)
    try:
        path = resolve_transcript(transcript_path)
        contents = read_transcript(path)
        transcript = Transcript.parse(contents, path.suffix.lower())
        logger.info("task_id=%s stage=transcript event=loaded turns=%d", self.request.id, len(transcript.turns))
        report = analyze_transcript(transcript)
        output_path = write_report(path, report)
        logger.info("task_id=%s stage=report event=written path=%s", self.request.id, output_path)
        logger.info("task_id=%s stage=task event=completed duration_s=%.2f", self.request.id, monotonic() - started)
    except Exception:
        logger.exception("task_id=%s stage=task event=failed duration_s=%.2f", self.request.id, monotonic() - started)
        raise
    finally:
        task_id.reset(token)
