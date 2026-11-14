# Podcast agent

Entry-point scaffold only: parsing and graph execution are deliberately unimplemented
pending review. No model calls or reports are produced yet.

## Layout

- `src/celery_app.py`: Celery configuration.
- `src/tasks.py`: queued entry point, bucket-key resolution and reading.
- `src/storage.py`: local mock-bucket path resolution and UTF-8 reading.
- `src/service.py`: shared parsing and graph invocation boundary.
- `src/graph.py`: graph invocation placeholder; topology comes next.
- `mock/`: local stand-in for an S3 bucket.

## Scaffold commands

Install with `uv sync`. With Redis running locally:

```sh
uv run celery -A src.celery_app:app worker --loglevel=INFO --concurrency=1
uv run celery -A src.celery_app:app call podcast_agent.analyze_episode \
  --args='["demo/ep001/transcript.json"]'
```

Set `CELERY_BROKER_URL` to override `redis://localhost:6379/0` in both producer
and worker environments. Both use the `podcast_agent` queue.

Tasks currently fail explicitly at the parser placeholder. Celery logs task
failures. Saving reports will be implemented in a later slice.
