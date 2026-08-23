#!/bin/bash
set -euo pipefail

BACKUP_FILE="${1:?Usage: restore.sh <backup_file> [db_name]}"
DB_NAME="${2:-huaqiao_free}"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "Restoring $DB_NAME from $BACKUP_FILE..."

if [[ "$BACKUP_FILE" == *.gz ]]; then
    gunzip -c "$BACKUP_FILE" | PGPASSWORD="${POSTGRES_PASSWORD:-huaqiao_dev}" psql -h localhost -U huaqiao "$DB_NAME"
else
    PGPASSWORD="${POSTGRES_PASSWORD:-huaqiao_dev}" psql -h localhost -U huaqiao "$DB_NAME" < "$BACKUP_FILE"
fi

echo "Restore complete."
