#!/bin/bash
set -euo pipefail

DB_NAME="${1:-huaqiao_free}"
BACKUP_DIR="${2:-/tmp/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "Backing up $DB_NAME to $BACKUP_FILE..."
PGPASSWORD="${POSTGRES_PASSWORD:-huaqiao_dev}" pg_dump -h localhost -U huaqiao "$DB_NAME" | gzip > "$BACKUP_FILE"

echo "Backup complete: $BACKUP_FILE"
echo "Size: $(du -h "$BACKUP_FILE" | cut -f1)"
