FROM ghcr.io/astral-sh/uv:0.11.19 AS uv
FROM python:3.13-slim

COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock ./
COPY src/ src/
RUN uv sync --frozen --no-dev

CMD ["celery", "-A", "src.celery_app:app", "worker", "--loglevel=INFO", "--concurrency=1"]
