# Быстрый старт: Запуск тестов API каталога

## Предварительные требования

1. **PostgreSQL** - должен быть запущен и доступен
2. **Redis** - для Celery очереди задач
3. **Python 3.10+** - с установленными зависимостями

## Шаг 1: Установка зависимостей

```bash
pip install -r requirements-dev.txt
```

## Шаг 2: Настройка тестовой базы данных

### Автоматически (рекомендуется)

**Windows (PowerShell):**
```powershell
.\setup_test_db.ps1
```

**Linux/Mac:**
```bash
chmod +x setup_test_db.sh
./setup_test_db.sh
```

### Вручную

```bash
# Создание БД
psql -U postgres -c "CREATE DATABASE momu_test;"

# Применение миграций
psql -U postgres -d momu_test -f app/migrations/init.sql
```

## Шаг 3: Запуск Redis и Celery

### Вариант A: Docker

```bash
# Redis
docker run -d -p 6379:6379 --name redis_test redis:latest

# Celery (в отдельном терминале)
cd app
celery -A core.celery_app worker --loglevel=info
```

### Вариант B: Docker Compose

```bash
docker-compose up redis celery
```

## Шаг 4: Запуск тестов

### Все тесты API каталога

```bash
pytest app/tests/api/test_catalog_api.py -v
```

### Конкретный тест

```bash
# Тест загрузки
pytest app/tests/api/test_catalog_api.py::test_catalog_upload_and_data_verification -v

# Тест удаления
pytest app/tests/api/test_catalog_api.py::test_catalog_delete_by_label -v

# Тест выгрузки
pytest app/tests/api/test_catalog_api.py::test_catalog_download -v

# Полный workflow
pytest app/tests/api/test_catalog_api.py::test_full_workflow -v
```

### С подробным выводом

```bash
pytest app/tests/api/test_catalog_api.py -v -s
```

### С покрытием кода

```bash
pytest app/tests/api/test_catalog_api.py --cov=app --cov-report=html
# Откройте htmlcov/index.html в браузере
```

## Структура тестов

```
app/tests/
├── conftest.py                    # Фикстуры для тестов
├── api/
│   ├── __init__.py
│   ├── test_catalog_api.py        # Тесты API каталога ⭐
│   └── README.md                  # Подробная документация
└── e2e/
    └── test_frontend.py           # E2E тесты с Playwright
```

## Что тестируется

✅ **Загрузка каталога** (`POST /api/v1/catalogs/upload_v2`)
- Загрузка Excel файла
- Обработка Celery задач
- Заполнение всех таблиц БД

✅ **Удаление по лейблу** (`DELETE /api/v1/catalogs/label/{label_id}`)
- Удаление всех данных лейбла
- Каскадное удаление связанных записей
- Очистка осиротевших записей

✅ **Выгрузка каталога** (`POST /api/v1/catalogs/download`)
- Экспорт данных в Excel
- Создание файла в storage

## Troubleshooting

### ❌ "Database connection failed"

Проверьте настройки в `.env.test` и что PostgreSQL запущен:

```bash
psql -U postgres -d momu_test -c "SELECT 1;"
```

### ❌ "TimeoutError: Задача не завершилась"

Убедитесь, что Celery worker запущен:

```bash
# В отдельном терминале
cd app
celery -A core.celery_app worker --loglevel=info
```

### ❌ "FAILED - Redis connection error"

Проверьте, что Redis запущен:

```bash
redis-cli ping
# Должен вернуть: PONG
```

### ❌ "File not found: test_upload_catalog.xlsx"

Убедитесь, что тестовый файл существует:

```bash
ls app/storage/test_upload_catalog.xlsx
```

## Очистка после тестов

```bash
# Удалить тестовую БД
psql -U postgres -c "DROP DATABASE momu_test;"

# Остановить Redis (если запускали через Docker)
docker stop redis_test
docker rm redis_test
```

## Дополнительная информация

Подробная документация в [app/tests/api/README.md](app/tests/api/README.md)
