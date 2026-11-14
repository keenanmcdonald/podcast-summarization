import os

from celery import Celery

app = Celery(
    "podcast_agent",
    broker=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    include=["src.tasks"],
)
app.conf.update(
    task_default_queue="podcast_agent",
    worker_prefetch_multiplier=1,
)
