#!/bin/sh
# Nightly backup (Milestone 14.3): compressed pg_dump + media sync, with
# 14-day retention. Run from host cron (see RUNBOOK.md):
#   0 3 * * *  cd /path/to/bbrose_design_os && sh scripts/backup.sh
#
# Works both against the compose stack (default) and a bare Postgres:
#   BACKUP_PG_MODE=compose  -> docker compose exec postgres pg_dump ...
#   BACKUP_PG_MODE=local    -> pg_dump $DATABASE_URL directly
set -eu

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
MODE="${BACKUP_PG_MODE:-compose}"
STAMP="$(date +%Y%m%d_%H%M%S)"

mkdir -p "$BACKUP_DIR"

echo "backup: database -> $BACKUP_DIR/db_$STAMP.dump"
if [ "$MODE" = "compose" ]; then
  # -Fc: custom format (compressed, pg_restore-able, supports partial restore)
  docker compose -f docker-compose.prod.yml exec -T postgres \
    pg_dump -U bbrose -Fc bbrose > "$BACKUP_DIR/db_$STAMP.dump"
else
  pg_dump -Fc "${DATABASE_URL:?BACKUP_PG_MODE=local needs DATABASE_URL}" \
    > "$BACKUP_DIR/db_$STAMP.dump"
fi

echo "backup: media -> $BACKUP_DIR/media_$STAMP.tar.gz"
if [ "$MODE" = "compose" ]; then
  docker compose -f docker-compose.prod.yml exec -T web \
    tar -czf - -C /app media > "$BACKUP_DIR/media_$STAMP.tar.gz"
else
  tar -czf "$BACKUP_DIR/media_$STAMP.tar.gz" -C "$(dirname "${MEDIA_ROOT:-./media}")" \
    "$(basename "${MEDIA_ROOT:-./media}")"
fi

echo "backup: pruning older than $RETENTION_DAYS days"
find "$BACKUP_DIR" -name 'db_*.dump' -mtime +"$RETENTION_DAYS" -delete
find "$BACKUP_DIR" -name 'media_*.tar.gz' -mtime +"$RETENTION_DAYS" -delete

echo "backup: done"
ls -lh "$BACKUP_DIR" | tail -5
