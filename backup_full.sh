#!/bin/bash
# ============================================
# Database backup script using pg_dump
# Usage: ./backup.sh [backup_dir]
# ============================================
set -euo pipefail

# Load .env if exists
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
fi

# Config
DB_CONTAINER="${DB_CONTAINER:-momu_postgres}"
DB_USER="${POSTGRES_USER:?POSTGRES_USER not set}"
DB_NAME="${POSTGRES_DB:?POSTGRES_DB not set}"
BACKUP_DIR="${1:-$SCRIPT_DIR/backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.dump"
KEEP_DAYS="${KEEP_DAYS:-7}"

# Create backup dir
mkdir -p "$BACKUP_DIR"

echo "🗄️  Starting backup: $DB_NAME → $BACKUP_FILE"
t0=$(date +%s)

docker exec "$DB_CONTAINER" pg_dump \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -Fc \
    --no-owner \
    --no-acl \
    > "$BACKUP_FILE"

t1=$(date +%s)
SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "✅ Backup complete: $SIZE in $((t1 - t0)) sec"

# Remove old backups
if [ "$KEEP_DAYS" -gt 0 ]; then
    DELETED=$(find "$BACKUP_DIR" -name "${DB_NAME}_*.dump" -mtime +"$KEEP_DAYS" -delete -print | wc -l)
    if [ "$DELETED" -gt 0 ]; then
        echo "🧹 Removed $DELETED old backup(s) (older than $KEEP_DAYS days)"
    fi
fi

echo "📂 Backups in $BACKUP_DIR:"
ls -lht "$BACKUP_DIR"/*.dump 2>/dev/null | head -5
