#!/bin/bash
set -e

host="$1"
shift

echo "⏳ Waiting for Postgres at $host..."

until psql "postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${host}:5432/${POSTGRES_DB}" -c '\q' >/dev/null 2>&1; do
  echo "Postgres is unavailable - sleeping"
  sleep 2
done

echo "✅ Postgres is up - starting application"
exec "$@"
