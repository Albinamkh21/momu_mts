import asyncio
import logging

import redis

from core.celery_app import celery_app
from core.config import settings
from core.database import SessionLocal
from telegram_integration.service import TelegramQueueService

logger = logging.getLogger(__name__)

POLL_LOCK_KEY = "telegram:poll-lock"


@celery_app.task(name="poll_telegram_orders")
def poll_telegram_orders() -> int:
    """Опрос Telegram и создание договоров из новых заявок. Запускается при старте приложения и по расписанию (celery beat)."""
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN не задан, опрос Telegram пропущен")
        return 0

    redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    # Защита от параллельных опросов (старт приложения и расписание могут совпасть)
    lock = redis_client.lock(POLL_LOCK_KEY, timeout=300, blocking=False)
    if not lock.acquire():
        logger.info("Опрос Telegram уже выполняется, пропускаем")
        return 0

    db = SessionLocal()
    try:
        service = TelegramQueueService(db, redis_client=redis_client)
        return asyncio.run(service.fetch_and_process_pending_orders())
    finally:
        db.close()
        if lock.owned():
            lock.release()
