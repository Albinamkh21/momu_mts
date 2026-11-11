import json
import logging
import redis
from sqlalchemy.orm import Session

from .client import TelegramAPIClient
from .schemas import IncomingContractPayload
from core.config import settings
from services.contract_service import ContractService
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
logger = logging.getLogger(__name__)

OFFSET_KEY = "telegram:last_update_id"

class TelegramQueueService:
    """Сервис опроса Telegram и создания договоров через существующий ContractService"""
    
    def __init__(self, db: Session, redis_client: redis.Redis = None):
        self.db = db
        self.client = TelegramAPIClient()
        self.contract_service = ContractService(db=db)
        # offset хранится в Redis, чтобы не обрабатывать одни и те же апдейты после перезапуска/нового запуска по расписанию
        self.redis = redis_client or redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

    def _load_offset(self) -> int:
        value = self.redis.get(OFFSET_KEY)
        return int(value) if value else 0

    def _save_offset(self, offset: int) -> None:
        self.redis.set(OFFSET_KEY, offset)

    async def fetch_and_process_pending_orders(self) -> int:
        """
        Опрашивает Telegram, забирает накопленные JSON-заявки от сайта,
        валидирует их через ExternalContractCreateRequest и создает договоры в БД + файлы .docx.
        Возвращает количество успешно обработанных заявок.
        """
        offset = self._load_offset()
        updates = await self.client.get_updates(offset=offset or None)
        processed_count = 0

        if not updates:
            return processed_count

        for update in updates:
            update_id = update.get("update_id")
            # Сдвигаем offset для подтверждения обработки и очистки очереди в Telegram
            

            message = update.get("message", {})
            text = message.get("text") or message.get("caption")

            if not text:
                continue

            try:
                # 1. Парсим текст сообщения как JSON
                raw_data = json.loads(text)
                
                # 2. Валидируем через реальную схему ExternalContractCreateRequest
                payload = IncomingContractPayload(**raw_data)
                
                # 3. Вызываем ваш реальный бизнес-метод создания контракта и генерации docx
                contract = self.contract_service.create_external_contract(payload)
                
                logger.info(f"✅ Успешно обработана заявка из Telegram, создан договор № {contract.contract_number}")
                processed_count += 1

                self._save_offset(update_id + 1)
                
            except json.JSONDecodeError:
                logger.warning(f"⚠️ Сообщение Telegram (ID: {update_id}) проигнорировано: текст не является JSON. Текст: {text}")
                self._save_offset(update_id + 1)
            except ValidationError as e:
                # ТЕПЕРЬ ЛОГИРУЕМ ОШИБКУ ВМЕСТЕ С ИСХОДНЫМ JSON (text), ЧТОБЫ ВИДЕТЬ ПРОБЛЕМУ
                logger.error(
                    f"❌ Ошибка валидации полей контракта для сообщения Telegram (ID: {update_id}). "
                    f"Ошибка: {e}. "
                    f"Полученный JSON: {text}"
                )
                self._save_offset(update_id + 1)
            except IntegrityError as e:
                self.db.rollback()
                logger.error(
                    f"⚠️ Конфликт данных (дубликат) для сообщения Telegram (ID: {update_id}): {e}. "
                    f"Договор с таким номером уже существует в базе."
                )
                self._save_offset(update_id + 1)    
            except Exception as e:
                self.db.rollback()
                logger.error(f"🔥 Ошибка при сохранении контракта из Telegram (ID: {update_id}): {e}")
                break

        return processed_count