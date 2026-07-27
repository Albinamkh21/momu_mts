import os
os.environ["POLARS_SKIP_CPU_CHECK"] = "true"
import sys
from pathlib import Path
from dotenv import load_dotenv
from core.celery_app import celery_app

def get_project_root() -> Path:
    """Динамически находит корень проекта (папку app)."""
    current = Path(__file__).resolve()
    # Ищем main.py, так как он лежит в корне /app
    for parent in [current] + list(current.parents):
        if (parent / 'main.py').exists():
            return parent
    
    # Фолбэк для контейнера
    return Path('/app')

PROJECT_ROOT = get_project_root()
PROJECT_ROOT_STR = str(PROJECT_ROOT)

# 1. Приоритет импортов
if PROJECT_ROOT_STR in sys.path:
    sys.path.remove(PROJECT_ROOT_STR)
sys.path.insert(0, PROJECT_ROOT_STR)

# 2. Очистка кэша pytest
if "api" in sys.modules and not hasattr(sys.modules["api"], "v1"):
    del sys.modules["api"]

# 3. Читаем .env.test
ENV_TEST_PATH = PROJECT_ROOT / '.env.test'
if not ENV_TEST_PATH.exists():
    raise RuntimeError(f"Файл {ENV_TEST_PATH} не найден внутри контейнера! Проверь volumes в docker-compose.")

load_dotenv(ENV_TEST_PATH, override=True)

# 4. Проверяем тестовую БД
TEST_DATABASE_URL = os.getenv("DATABASE_URL_TEST")

if not TEST_DATABASE_URL:
    raise RuntimeError("Переменная 'DATABASE_URL_TEST' не найдена в .env.test")

if not TEST_DATABASE_URL.endswith("momu_test"):
    raise RuntimeError(f"ОПАСНОСТЬ! База {TEST_DATABASE_URL} не является тестовой (не оканчивается на momu_test)")
    



import pytest
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from dotenv import load_dotenv


@pytest.fixture(autouse=True)
def enable_celery_sync():
    # Включаем режим Eager (синхронное выполнение) на время тестов
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True  # чтобы исключения из задач прокидывались в тесты
    )
    yield

@pytest.fixture(scope="session")
def test_engine():
    """Создаём движок для тестовой БД."""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"options": "-csearch_path=public"}) 
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def test_session_factory(test_engine):
    """Фабрика сессий для тестов."""
    return sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session(test_session_factory):
    """Создаём сессию для каждого теста."""
    session = test_session_factory()
    yield session
    session.close()


@pytest.fixture(scope="function")
def clean_test_db(test_engine):
    """Быстро очищает тестовую БД перед каждым тестом."""
    with test_engine.begin() as conn:
        conn.execute(text("""
            TRUNCATE TABLE 
                report_track_rights_cache,
                staging_catalog_v2,
                staging_person
            RESTART IDENTITY CASCADE;
        """))
    yield


@pytest.fixture(scope="session")
def api_client():
    """Создаём тестовый клиент FastAPI."""
    from main import app
    return TestClient(app)
