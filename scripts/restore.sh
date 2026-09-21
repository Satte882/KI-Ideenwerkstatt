#!/bin/sh
set -eu
if [ "$#" -ne 1 ]; then echo "Usage: restore.sh /backups/file.dump" >&2; exit 2; fi
FILE="$1"
: "${RESTORE_DATABASE:?Set RESTORE_DATABASE to a non-production database name}"
case "$RESTORE_DATABASE" in
  "${POSTGRES_DB:-ki_radar}") echo "Refusing to restore into configured production database" >&2; exit 3 ;;
esac
export PGPASSWORD="$(cat /run/secrets/db_password)"
createdb -h "${POSTGRES_HOST:-db}" -U "${POSTGRES_USER:-ki_radar}" "$RESTORE_DATABASE" 2>/dev/null || true
pg_restore --clean --if-exists --no-owner -h "${POSTGRES_HOST:-db}" -U "${POSTGRES_USER:-ki_radar}" -d "$RESTORE_DATABASE" "$FILE"
echo "Restore completed into $RESTORE_DATABASE"
