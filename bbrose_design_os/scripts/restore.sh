#!/bin/sh
# Restore a backup made by scripts/backup.sh (Milestone 14.3). DESTRUCTIVE:
# recreates the target database from the dump. See RUNBOOK.md for the full
# procedure (stop workers first, verify after).
#
#   sh scripts/restore.sh backups/db_20260703_030000.dump [backups/media_...tar.gz]
#
#   BACKUP_PG_MODE=compose (default) restores into the compose postgres;
#   BACKUP_PG_MODE=local restores into RESTORE_DATABASE_URL.
set -eu

DUMP="${1:?usage: restore.sh <db.dump> [media.tar.gz]}"
MEDIA_TAR="${2:-}"
MODE="${BACKUP_PG_MODE:-compose}"

echo "restore: database from $DUMP"
if [ "$MODE" = "compose" ]; then
  # --clean --if-exists: drop + recreate objects inside the existing DB.
  docker compose -f docker-compose.prod.yml exec -T postgres \
    pg_restore -U bbrose -d bbrose --clean --if-exists --no-owner < "$DUMP"
else
  pg_restore -d "${RESTORE_DATABASE_URL:?BACKUP_PG_MODE=local needs RESTORE_DATABASE_URL}" \
    --clean --if-exists --no-owner "$DUMP"
fi

if [ -n "$MEDIA_TAR" ]; then
  echo "restore: media from $MEDIA_TAR"
  if [ "$MODE" = "compose" ]; then
    docker compose -f docker-compose.prod.yml exec -T web \
      tar -xzf - -C /app < "$MEDIA_TAR"
  else
    tar -xzf "$MEDIA_TAR" -C "$(dirname "${MEDIA_ROOT:-./media}")"
  fi
fi

echo "restore: done — verify with: manage.py check && a dashboard login"
