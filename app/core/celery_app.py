import os
from celery import Celery
from celery.signals import setup_logging as celery_setup_logging

from core.config import setup_logging

REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://momu_redis:6379/0")

celery_app = Celery(
    "momu_project",
    broker=os.getenv("CELERY_BROKER_URL", "redis://momu_redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://momu_redis:6379/0"),
    include=["tasks.catalog_tasks", "tasks.report_tasks", "tasks.catalog_tasks_v2", "tasks.telegram_tasks"],
)


@celery_setup_logging.connect
def _configure_file_logging(**kwargs):
    # Подключение обработчика отключает встроенную настройку логов Celery, поэтому наши хендлеры (файлы + консоль) сохраняются.
    setup_logging()


celery_app.conf.update(
    task_track_started=True,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Europe/Moscow',
    enable_utc=True,
    task_name_rewrite=None
)

# Интервал опроса Telegram в секундах (запуск через celery beat)
celery_app.conf.beat_schedule = {
    "poll-telegram-orders": {
        "task": "poll_telegram_orders",
        "schedule": int(os.getenv("TELEGRAM_POLL_INTERVAL_SECONDS", "300")),
    },
}


