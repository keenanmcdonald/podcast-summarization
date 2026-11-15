#!/bin/sh
set -eu

cd "$(dirname "$0")/.."

set -- mock/demo/ep*/transcript.json
if [ ! -f "$1" ]; then
    echo "No demo transcripts found under mock/demo/" >&2
    exit 1
fi

for transcript do
    key=${transcript#mock/}
    printf 'Queued %s: ' "$key"
    celery -A src.celery_app:app call podcast_agent.analyze_episode \
        --args="[\"$key\"]"
    printf '  Report: %s/report.json\n' "${transcript%/*}"
done

printf '\nTasks run in the background. On the host: docker compose logs -f worker\n'
