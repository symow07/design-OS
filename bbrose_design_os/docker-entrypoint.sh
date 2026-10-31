#!/bin/sh
# Entrypoint (Milestone 14.3): wait for Postgres, run migrations, collect
# static (hashed manifest storage — compose sets USE_MANIFEST_STATIC=true),
# then exec the container command (gunicorn for web, celery for worker).
#
# Deliberately plain POSIX sh: the DB wait is a simple counted loop around
# `python -c` (no heredocs) and this script is exercised by
# apps/pipeline/tests/test_phase14.py::EntrypointScriptTests, so a syntax
# error fails the test suite, not the first container boot.
set -e

if [ -n "$DATABASE_URL" ]; then
  echo "entrypoint: waiting for database..."
  i=0
  while true; do
    if python -c 'import os, psycopg2; psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=3).close()' 2>/dev/null; then
      break
    fi
    i=$((i + 1))
    if [ "$i" -ge 30 ]; then
      echo "entrypoint: database never became ready" >&2
      exit 1
    fi
    sleep 2
  done
  echo "entrypoint: database is ready"
fi

# Only the web container migrates/collects (worker sets SKIP_DJANGO_SETUP=1)
# so parallel startup doesn't race two `migrate` runs.
if [ "$SKIP_DJANGO_SETUP" != "1" ]; then
  echo "entrypoint: applying migrations..."
  python manage.py migrate --noinput
  echo "entrypoint: collecting static files..."
  python manage.py collectstatic --noinput
fi

exec "$@"
