#!/bin/sh
set -e

if [ -z "$DATABASE_URL" ]; then
  echo "Waiting for postgres..."
  while ! nc -z ${POSTGRES_HOST:-db} ${POSTGRES_PORT:-5432}; do
    sleep 0.1
  done
  echo "PostgreSQL started"
fi

python manage.py migrate
python manage.py collectstatic --no-input

if [ ! -d "/app/nlp_models/urchade_gliner_medium_v2_1" ]; then
  echo "GLiNER model not found — downloading from HuggingFace (this may take a few minutes)..."
  python manage.py download_model
fi

exec "$@"
