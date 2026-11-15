# Podcast analysis agent

One agent reads a transcript, researches factual assertions with Tavily, and returns a structured report containing a summary, five takeaways, quotes, topics, and fact checks. Each fact check retains the claim's timestamped occurrences, verdict, rationale, and evidence references.

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

The script runs inside the worker container and queues the JSON transcripts for `ep001`, `ep002`, and `ep003`. Each Celery worker processes one episode at a time using a synchronous, search-capable agent. It prints each task ID and report path (`mock/demo/ep001/report.json`, etc., on the host). Tasks run in the background; check the logs for completion before reading reports. Stop with `docker compose down`.

## Implementation

- `src/agent/run.py`: agent construction and one output-correction attempt.
- `src/agent/prompt.md`: the single system prompt for notes, claim selection, and verification.
- `src/agent/validation.py`: checks quotes, transcript references, and source provenance.
- `src/agent/tools/search.py`: synchronous search tool.
- `src/models/`: Pydantic transcript and report models, shared through the application.
- `src/tasks.py`, `src/storage.py`: task execution and atomic report storage.

The agent uses `gpt-6-sol` with medium reasoning effort. Each episode has a budget of 30 model calls, shared with the correction attempt. Provider requests have 30-second timeouts; model requests may retry twice for transient errors. Celery's prefork worker enforces a 300-second soft task limit and a 330-second hard limit. These execution limits apply to queued tasks, not direct calls to the analysis function.

Reports that pass the provider's structured-output schema but fail transcript or source-reference checks receive one correction attempt with the existing conversation. Provider schema parse errors, persistent reference errors, an exhausted model-call budget, and model-provider failures fail the task without replacing an existing report. Search failures are logged and returned to the agent as generic errors, distinct from a successful search with no matches. Validation checks transcript references and search-result URLs/titles (tolerating only a `www.` host difference), not whether every assertion was identified or whether cited evidence supports the verdict; those require quality evaluation.

Run the offline tests with `uv run python -m unittest discover -s tests -v`. Tests use scripted model responses and mocked search calls, not live providers.

## Tracing

Traces contain the episode analysis, model calls, search calls and results, output corrections, and provider-returned reasoning summaries when available. Provider-returned reasoning summaries, when available, are also written to worker logs. Queue the demos using the commands above after starting Compose. Traces and reasoning-summary logs can contain transcript-derived details; configure access, retention, and redaction before processing sensitive data.

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
