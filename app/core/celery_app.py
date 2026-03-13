import os
from celery import Celery

REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://momu_redis:6379/0")

celery_app = Celery(
    "momu_project",
    broker=os.getenv("CELERY_BROKER_URL", "redis://momu_redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://momu_redis:6379/0"),
    include=["tasks.catalog_tasks", "tasks.report_tasks"],
)


celery_app.conf.update(
    task_track_started=True,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Europe/Moscow',
    enable_utc=True,
    task_name_rewrite=None
)


