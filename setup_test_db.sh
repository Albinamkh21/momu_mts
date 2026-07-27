#!/bin/bash

# Скрипт для инициализации тестовой базы данных
# Использование: ./setup_test_db.sh

set -e

echo "🔧 Настройка тестовой базы данных momu_test..."

# Проверяем наличие .env.test
if [ ! -f ".env.test" ]; then
    echo "❌ Файл .env.test не найден!"
    exit 1
fi

# Загружаем переменные из .env.test
source .env.test

echo "📊 Настройки подключения:"
echo "  Host: ${POSTGRES_HOST}"
echo "  Port: ${POSTGRES_PORT}"
echo "  User: ${POSTGRES_USER}"
echo "  Database: ${POSTGRES_DB}"

# Проверяем подключение к PostgreSQL
echo ""
echo "🔍 Проверка подключения к PostgreSQL..."
if ! PGPASSWORD=${POSTGRES_PASSWORD} psql -h ${POSTGRES_HOST} -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -d postgres -c "\q" 2>/dev/null; then
    echo "❌ Не удалось подключиться к PostgreSQL"
    echo "   Убедитесь, что PostgreSQL запущен и настройки в .env.test корректны"
    exit 1
fi
echo "✅ Подключение успешно"

# Проверяем существование БД
echo ""
echo "🔍 Проверка существования БД ${POSTGRES_DB}..."
DB_EXISTS=$(PGPASSWORD=${POSTGRES_PASSWORD} psql -h ${POSTGRES_HOST} -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${POSTGRES_DB}'")

if [ "$DB_EXISTS" = "1" ]; then
    echo "⚠️  База данных ${POSTGRES_DB} уже существует"
    read -p "   Удалить и создать заново? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🗑️  Удаление базы данных..."
        PGPASSWORD=${POSTGRES_PASSWORD} psql -h ${POSTGRES_HOST} -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -d postgres -c "DROP DATABASE IF EXISTS ${POSTGRES_DB};"
        echo "✅ База данных удалена"
    else
        echo "⏭️  Пропускаем создание базы данных"
        CREATE_DB=false
    fi
fi

# Создаём БД если нужно
if [ "$CREATE_DB" != "false" ]; then
    echo ""
    echo "📦 Создание базы данных ${POSTGRES_DB}..."
    PGPASSWORD=${POSTGRES_PASSWORD} psql -h ${POSTGRES_HOST} -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -d postgres -c "CREATE DATABASE ${POSTGRES_DB};"
    echo "✅ База данных создана"
fi

# Применяем миграции
echo ""
echo "🚀 Применение миграций из app/migrations/init.sql..."
if [ ! -f "app/migrations/init.sql" ]; then
    echo "❌ Файл app/migrations/init.sql не найден!"
    exit 1
fi

PGPASSWORD=${POSTGRES_PASSWORD} psql -h ${POSTGRES_HOST} -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -d ${POSTGRES_DB} -f app/migrations/init.sql

echo "✅ Миграции применены"

# Проверяем создание таблиц
echo ""
echo "🔍 Проверка созданных таблиц..."
TABLE_COUNT=$(PGPASSWORD=${POSTGRES_PASSWORD} psql -h ${POSTGRES_HOST} -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -d ${POSTGRES_DB} -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';")

if [ "$TABLE_COUNT" -gt 0 ]; then
    echo "✅ Создано таблиц: ${TABLE_COUNT}"
    echo ""
    echo "📋 Список основных таблиц:"
    PGPASSWORD=${POSTGRES_PASSWORD} psql -h ${POSTGRES_HOST} -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "\dt" | grep -E "(label|track|person|release|right_holder)" || true
else
    echo "⚠️  Таблицы не обнаружены, возможно миграции не применились корректно"
fi

echo ""
echo "✅ Тестовая база данных готова к использованию!"
echo ""
echo "📝 Следующие шаги:"
echo "   1. Убедитесь, что Redis запущен: docker run -d -p 6379:6379 redis:latest"
echo "   2. Запустите Celery worker: cd app && celery -A core.celery_app worker --loglevel=info"
echo "   3. Запустите тесты: pytest app/tests/api/test_catalog_api.py -v"
echo ""
