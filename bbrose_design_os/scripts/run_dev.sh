#!/bin/sh
# Dev runner (hardening 2026-07-04): worker mode needs BOTH processes — with
# real API keys a pipeline run takes minutes and must not run inside the HTTP
# request (eager mode would hang the browser on task creation).
# Starts a Celery worker in the background + runserver in the foreground;
# Ctrl-C stops both.
set -e
cd "$(dirname "$0")/.."
if ! redis-cli ping >/dev/null 2>&1; then
  echo "redis is not running — start it with: brew services start redis" >&2
  exit 1
fi
venv/bin/celery -A config worker --loglevel=info --concurrency=2 &
WORKER=$!
trap 'kill $WORKER 2>/dev/null' EXIT INT TERM
venv/bin/python manage.py runserver
