# Тесты для API каталога

## Описание

Этот модуль содержит тесты для API управления каталогами музыкальных треков.

## Тестируемые эндпоинты

1. **POST /api/v1/catalogs/upload_v2** - Загрузка каталога из Excel файла
2. **DELETE /api/v1/catalogs/label/{label_id}** - Удаление всех данных по лейблу
3. **POST /api/v1/catalogs/download** - Выгрузка каталога в Excel файл

## Структура тестов

### test_catalog_upload_and_data_verification
Проверяет загрузку каталога и корректное заполнение всех таблиц:
- `staging_catalog_v2` - промежуточная таблица загрузки
- `staging_person` - промежуточная таблица персон
- `label` - лейблы
- `person` - персоны (артисты, композиторы, авторы текстов)
- `right_holder` - правообладатели
- `release` - релизы/альбомы
- `track` - треки
- `track_contribution` - связи треков и персон
- `track_right` - права на треки
- `track_label` - связи треков и лейблов
- `track_release` - связи треков и релизов

### test_catalog_delete_by_label
Проверяет удаление всех данных по конкретному лейблу:
1. Загружает каталог
2. Удаляет данные через API
3. Проверяет, что все связанные данные корректно удалены
4. Проверяет удаление осиротевших записей (треки без лейблов, релизы без треков, персоны без вкладов)

### test_catalog_download
Проверяет выгрузку каталога:
1. Загружает каталог
2. Запускает выгрузку
3. Проверяет создание файла

### test_full_workflow
Комплексный тест полного рабочего процесса:
1. Загрузка → 2. Проверка → 3. Выгрузка → 4. Удаление → 5. Проверка удаления

## Подготовка к запуску тестов

### 1. Создание тестовой базы данных

```bash
# Подключитесь к PostgreSQL
psql -U postgres

# Создайте тестовую БД
CREATE DATABASE momu_test;

# Подключитесь к тестовой БД
\c momu_test

# Выполните миграции из init.sql
\i app/migrations/init.sql
```

Или через docker:

```bash
# Если используете docker-compose, добавьте создание БД
docker exec -it momu_db psql -U postgres -c "CREATE DATABASE momu_test;"

# Примените миграции
docker exec -it momu_db psql -U postgres -d momu_test -f /app/migrations/init.sql
```

### 2. Настройка окружения

Убедитесь, что файл `.env.test` существует в корне проекта и содержит правильные настройки:

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=momu_test
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

DATABASE_URL=postgresql://postgres:postgres@localhost:5432/momu_test

REDIS_URL=redis://localhost:6379/1
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

### 3. Запуск Redis и Celery

Тесты используют Celery для асинхронной обработки задач, поэтому необходимо запустить:

```bash
# Запуск Redis (если ещё не запущен)
docker run -d -p 6379:6379 redis:latest

# Запуск Celery worker (из директории проекта)
cd app
celery -A core.celery_app worker --loglevel=info
```

Или через docker-compose:

```bash
docker-compose up redis celery
```

### 4. Тестовый файл

Убедитесь, что файл `app/storage/test_upload_catalog.xlsx` существует и содержит тестовые данные.

## Запуск тестов

### Запуск всех тестов API каталога

```bash
# Из корня проекта
pytest app/tests/api/test_catalog_api.py -v

# Или с подробным выводом
pytest app/tests/api/test_catalog_api.py -v -s
```

### Запуск конкретного теста

```bash
# Тест загрузки
pytest app/tests/api/test_catalog_api.py::test_catalog_upload_and_data_verification -v

# Тест удаления
pytest app/tests/api/test_catalog_api.py::test_catalog_delete_by_label -v

# Тест выгрузки
pytest app/tests/api/test_catalog_api.py::test_catalog_download -v

# Полный рабочий процесс
pytest app/tests/api/test_catalog_api.py::test_full_workflow -v
```

### Запуск с покрытием кода

```bash
pytest app/tests/api/test_catalog_api.py --cov=app --cov-report=html
```

## Troubleshooting

### Ошибка подключения к БД

Если тесты не могут подключиться к тестовой БД:
1. Проверьте, что PostgreSQL запущен
2. Проверьте настройки в `.env.test`
3. Убедитесь, что БД `momu_test` создана
4. Проверьте, что применены миграции

### Timeout при ожидании Celery задач

Если тесты падают с TimeoutError:
1. Проверьте, что Celery worker запущен
2. Проверьте, что Redis доступен
3. Увеличьте timeout в функции `wait_for_celery_task`
4. Проверьте логи Celery worker

### Ошибки целостности данных

Если появляются ошибки foreign key violations:
1. Убедитесь, что миграции применены корректно
2. Проверьте, что fixture `clean_test_db` очищает таблицы в правильном порядке
3. Проверьте, что в `init.sql` есть все необходимые функции и триггеры

## Дополнительные команды

### Очистка тестовой БД вручную

```bash
psql -U postgres -d momu_test -c "TRUNCATE TABLE report_track_rights_cache, track_contribution, track_right, track_release, track_label, track, release, person, right_holder, label, staging_catalog_v2, staging_person RESTART IDENTITY CASCADE;"
```

### Просмотр данных в тестовой БД

```bash
# Подключение к БД
psql -U postgres -d momu_test

# Примеры запросов
SELECT COUNT(*) FROM track;
SELECT COUNT(*) FROM label;
SELECT * FROM label;
```

## Примечания

- Тесты используют реальную БД `momu_test`, а не моки
- Каждый тест очищает БД перед запуском через fixture `clean_test_db`
- Тесты асинхронные и ожидают завершения Celery задач
- Тестовый файл `test_upload_catalog.xlsx` должен содержать корректные данные

## CI/CD

Для интеграции в CI/CD pipeline добавьте в `.github/workflows` или аналог:

```yaml
- name: Run catalog API tests
  run: |
    pytest app/tests/api/test_catalog_api.py -v --junitxml=test-results.xml
  env:
    DATABASE_URL: postgresql://postgres:postgres@localhost:5432/momu_test
```
