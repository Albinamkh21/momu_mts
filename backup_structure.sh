#!/bin/bash

# ============================================
# Мета-бэкап: Вся структура + Данные справочников
# ============================================

set -euo pipefail

# Загружаем окружение
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
fi

# Конфиг
DB_CONTAINER="${DB_CONTAINER:-momu_postgres}"
DB_USER="${POSTGRES_USER:?POSTGRES_USER not set}"
DB_NAME="${POSTGRES_DB:?POSTGRES_DB not set}"
BACKUP_DIR="${1:-$SCRIPT_DIR/backups_meta}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_meta_${TIMESTAMP}.sql"

mkdir -p "$BACKUP_DIR"

echo "📑 Шаг 1: Экспорт структуры всех таблиц..."
# -s (или --schema-only) выгружает только структуру
docker exec "$DB_CONTAINER" pg_dump \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -s \
    --no-owner \
    --no-acl \
    > "$BACKUP_FILE"

echo "📊 Шаг 2: Добавление данных справочников..."
# -a (или --data-only) выгружает только строки
# --column-inserts делает бэкап более читаемым и надежным для SQL
docker exec "$DB_CONTAINER" pg_dump \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -a \
    --column-inserts \
    -t partners \
    -t finding_source \
    -t label \
    -t right_usage_type \
    -t right_category \
    -t region \
    --no-owner \
    --no-acl \
    >> "$BACKUP_FILE"

echo "✅ Бэкап готов: $BACKUP_FILE"
echo "Размер: $(du -h "$BACKUP_FILE" | cut -f1)"