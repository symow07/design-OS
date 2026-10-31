# Production image (Milestone 14.3). Built from the pinned lock; the same
# image runs the web (gunicorn) and the Celery worker (compose overrides the
# command). NOTE: docker was not available on the dev machine when this was
# authored — validate with `docker compose -f docker-compose.prod.yml build`
# on the deploy host before first use.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# psql client for the backup job / entrypoint DB wait.
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN chmod +x docker-entrypoint.sh \
    && useradd --create-home appuser \
    && mkdir -p /app/media /app/staticfiles \
    && chown -R appuser:appuser /app
USER appuser

ENTRYPOINT ["./docker-entrypoint.sh"]
# gthread: SSE task-event streams (Milestone 13.2) hold a connection for up to
# ~5 min; threaded workers keep them from starving the pool.
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", "--worker-class", "gthread", "--threads", "8", \
     "--timeout", "120", "--access-logfile", "-"]
