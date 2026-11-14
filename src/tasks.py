import asyncio
import logging

from src.agent.models.transcript import Transcript
from src.celery_app import app
from src.service import analyze_transcript
from src.storage import read_transcript, resolve_transcript

logger = logging.getLogger(__name__)


@app.task(bind=True, name="podcast_agent.analyze_episode")
def analyze_episode(self, transcript_path: str) -> None:
    logger.info("task_id=%s transcript=%s", self.request.id, transcript_path)
    path = resolve_transcript(transcript_path)
    contents = read_transcript(path)
    transcript = Transcript.parse(contents, path.suffix.lower())
    asyncio.run(analyze_transcript(transcript))
    raise NotImplementedError("Saving the report awaits implementation")
