#!/bin/sh
set -e

# Written once setup has finished; the backend's healthcheck looks for it so
# the worker only starts after migrations have run. Cleared first so a
# restarted container doesn't report healthy before its own setup completes.
SETUP_MARKER=/tmp/setup-complete
rm -f "$SETUP_MARKER"

if [ -z "$DATABASE_URL" ]; then
  echo "Waiting for postgres..."
  while ! nc -z ${POSTGRES_HOST:-db} ${POSTGRES_PORT:-5432}; do
    sleep 0.1
  done
  echo "PostgreSQL started"
fi

# Containers sharing this image (backend and worker) must not all run setup:
# concurrent `migrate` runs race on the same tables and one of them crashes,
# and concurrent GLiNER downloads write into the same shared volume. Only the
# container with RUN_SETUP unset or true does it; the others wait for it.
if [ "${RUN_SETUP:-true}" = "true" ]; then
  python manage.py migrate
  python manage.py collectstatic --no-input

  if [ ! -d "/app/nlp_models/urchade_gliner_medium_v2_1" ]; then
    echo "GLiNER model not found — downloading from HuggingFace (this may take a few minutes)..."
    python manage.py download_model
  fi
fi

touch "$SETUP_MARKER"

exec "$@"
