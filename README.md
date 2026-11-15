# Podcast analysis agent

## How to run

Requires OpenAI and Tavily API keys. Tracing defaults to LangSmith, so add a LangSmith API key too (or use Jaeger below). Create `.env` in the repository root:

```dotenv
OPENAI_API_KEY=...
TAVILY_API_KEY=...
LANGSMITH_API_KEY=...
```

Run from the repository root:

```sh
docker compose up --build -d
docker compose exec worker ./scripts/run-demos.sh
docker compose logs -f worker
```

The script runs inside the worker container and queues the JSON transcripts for `ep001`, `ep002`, and `ep003`. Celery processes one episode at a time per worker; claims within an episode can be checked concurrently. It prints each task ID and report path (`mock/demo/ep001/report.json`, etc., on the host). Tasks run in the background; check the logs for completion before reading reports. Stop with `docker compose down`.

## Tracing

Tracing lets you inspect graph execution, model calls, and per-claim work. Queue the demos using the commands above after starting Compose.

### LangSmith

With `LANGSMITH_API_KEY` in `.env`, run `docker compose up --build -d` and inspect runs in [LangSmith](https://smith.langchain.com/). No other tracing settings are needed.

```dotenv
LANGSMITH_API_KEY=...
```

### Jaeger

For local traces without a LangSmith key, omit `LANGSMITH_API_KEY` and add to `.env`:

```dotenv
LANGSMITH_TRACING_MODE=otel
```

Run `docker compose up --build -d`, then open [http://localhost:16686](http://localhost:16686) and select `podcast-summarization`. Jaeger starts with Compose in either tracing mode and stores traces in memory; stopping it erases them.

To send traces to both viewers, use `LANGSMITH_TRACING_MODE=hybrid` with a LangSmith API key. To disable tracing, set `LANGSMITH_TRACING=false`. After changing settings, recreate the worker with `docker compose up -d --force-recreate`, then queue the demos again.
