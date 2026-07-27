# PowerShell script для инициализации тестовой базы данных
# Использование: .\setup_test_db.ps1

$ErrorActionPreference = "Stop"

Write-Host "🔧 Настройка тестовой базы данных momu_test..." -ForegroundColor Cyan

# Проверяем наличие .env.test
if (-not (Test-Path ".env.test")) {
    Write-Host "❌ Файл .env.test не найден!" -ForegroundColor Red
    exit 1
}

# Загружаем переменные из .env.test
Get-Content ".env.test" | ForEach-Object {
    if ($_ -match "^([^=]+)=(.*)$") {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        Set-Item -Path "env:$name" -Value $value
    }
}

Write-Host "`n📊 Настройки подключения:" -ForegroundColor Yellow
Write-Host "  Host: $env:POSTGRES_HOST"
Write-Host "  Port: $env:POSTGRES_PORT"
Write-Host "  User: $env:POSTGRES_USER"
Write-Host "  Database: $env:POSTGRES_DB"

# Проверяем подключение к PostgreSQL
Write-Host "`n🔍 Проверка подключения к PostgreSQL..." -ForegroundColor Yellow
$env:PGPASSWORD = $env:POSTGRES_PASSWORD
try {
    $null = psql -h $env:POSTGRES_HOST -p $env:POSTGRES_PORT -U $env:POSTGRES_USER -d postgres -c "\q" 2>&1
    Write-Host "✅ Подключение успешно" -ForegroundColor Green
} catch {
    Write-Host "❌ Не удалось подключиться к PostgreSQL" -ForegroundColor Red
    Write-Host "   Убедитесь, что PostgreSQL запущен и настройки в .env.test корректны" -ForegroundColor Red
    exit 1
}

# Проверяем существование БД
Write-Host "`n🔍 Проверка существования БД $env:POSTGRES_DB..." -ForegroundColor Yellow
$dbExists = psql -h $env:POSTGRES_HOST -p $env:POSTGRES_PORT -U $env:POSTGRES_USER -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$env:POSTGRES_DB'"

if ($dbExists -eq "1") {
    Write-Host "⚠️  База данных $env:POSTGRES_DB уже существует" -ForegroundColor Yellow
    $response = Read-Host "   Удалить и создать заново? (y/N)"
    if ($response -match "^[Yy]$") {
        Write-Host "🗑️  Удаление базы данных..." -ForegroundColor Yellow
        psql -h $env:POSTGRES_HOST -p $env:POSTGRES_PORT -U $env:POSTGRES_USER -d postgres -c "DROP DATABASE IF EXISTS $env:POSTGRES_DB;"
        Write-Host "✅ База данных удалена" -ForegroundColor Green
        $createDb = $true
    } else {
        Write-Host "⏭️  Пропускаем создание базы данных" -ForegroundColor Yellow
        $createDb = $false
    }
} else {
    $createDb = $true
}

# Создаём БД если нужно
if ($createDb) {
    Write-Host "`n📦 Создание базы данных $env:POSTGRES_DB..." -ForegroundColor Yellow
    psql -h $env:POSTGRES_HOST -p $env:POSTGRES_PORT -U $env:POSTGRES_USER -d postgres -c "CREATE DATABASE $env:POSTGRES_DB;"
    Write-Host "✅ База данных создана" -ForegroundColor Green
}

# Применяем миграции
Write-Host "`n🚀 Применение миграций из app/migrations/init.sql..." -ForegroundColor Yellow
if (-not (Test-Path "app/migrations/init.sql")) {
    Write-Host "❌ Файл app/migrations/init.sql не найден!" -ForegroundColor Red
    exit 1
}

psql -h $env:POSTGRES_HOST -p $env:POSTGRES_PORT -U $env:POSTGRES_USER -d $env:POSTGRES_DB -f app/migrations/init.sql

Write-Host "✅ Миграции применены" -ForegroundColor Green

# Проверяем создание таблиц
Write-Host "`n🔍 Проверка созданных таблиц..." -ForegroundColor Yellow
$tableCount = psql -h $env:POSTGRES_HOST -p $env:POSTGRES_PORT -U $env:POSTGRES_USER -d $env:POSTGRES_DB -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';"

if ([int]$tableCount -gt 0) {
    Write-Host "✅ Создано таблиц: $tableCount" -ForegroundColor Green
    Write-Host "`n📋 Список основных таблиц:" -ForegroundColor Yellow
    psql -h $env:POSTGRES_HOST -p $env:POSTGRES_PORT -U $env:POSTGRES_USER -d $env:POSTGRES_DB -c "\dt"
} else {
    Write-Host "⚠️  Таблицы не обнаружены, возможно миграции не применились корректно" -ForegroundColor Yellow
}

Write-Host "`n✅ Тестовая база данных готова к использованию!" -ForegroundColor Green
Write-Host "`n📝 Следующие шаги:" -ForegroundColor Cyan
Write-Host "   1. Убедитесь, что Redis запущен: docker run -d -p 6379:6379 redis:latest"
Write-Host "   2. Запустите Celery worker: cd app; celery -A core.celery_app worker --loglevel=info"
Write-Host "   3. Запустите тесты: pytest app/tests/api/test_catalog_api.py -v"
Write-Host ""
