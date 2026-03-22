#!/bin/sh
set -e

echo "Waiting for postgres..."
while ! nc -z ${POSTGRES_HOST:-db} ${POSTGRES_PORT:-5432}; do
  sleep 0.1
done
echo "PostgreSQL started"

python manage.py migrate
python manage.py collectstatic --no-input

exec "$@"
