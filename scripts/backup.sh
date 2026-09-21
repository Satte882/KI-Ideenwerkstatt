#!/bin/sh
set -eu
STARTED_AT="$(date -Iseconds)"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
FILE="$BACKUP_DIR/daily/ki-radar-$STAMP.dump"
mkdir -p "$BACKUP_DIR/daily" "$BACKUP_DIR/monthly"
record_failure() {
  python manage.py record_job_run database_backup --status failed --started-at "$STARTED_AT" --exit-code 1 --error "$1" || true
}
trap 'record_failure "Backup script failed"' INT TERM HUP EXIT
export PGPASSWORD="$(cat /run/secrets/db_password)"
pg_dump -Fc -h "${POSTGRES_HOST:-db}" -U "${POSTGRES_USER:-ki_radar}" -d "${POSTGRES_DB:-ki_radar}" -f "$FILE"
pg_restore --list "$FILE" >/dev/null
find "$BACKUP_DIR/daily" -type f -name '*.dump' -mtime +14 -delete
if [ "$(date +%d)" = "01" ]; then
  cp "$FILE" "$BACKUP_DIR/monthly/"
fi
find "$BACKUP_DIR/monthly" -type f -name '*.dump' -mtime +100 -delete
if [ -n "${RCLONE_REMOTE:-}" ] && command -v rclone >/dev/null 2>&1; then
  rclone copy "$FILE" "$RCLONE_REMOTE"
fi
SIZE="$(wc -c < "$FILE")"
python manage.py record_job_run database_backup --status success --started-at "$STARTED_AT" --details "{\"file\":\"$FILE\",\"size_bytes\":$SIZE}"
trap - INT TERM HUP EXIT
printf 'Backup created: %s\n' "$FILE"
