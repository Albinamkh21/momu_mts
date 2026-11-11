import httpx
import logging
from typing import List, Dict, Any
from core.config import settings

logger = logging.getLogger(__name__)

class TelegramAPIClient:
    """Низкоуровневый клиент для взаимодействия с Telegram Bot API через httpx"""
    
    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    async def get_updates(self, offset: int = None) -> List[Dict[str, Any]]:
        """Запрос новых сообщений (очереди) от серверов Telegram"""
        url = f"{self.base_url}/getUpdates"
        params = {"timeout": 5}
        if offset:
            params["offset"] = offset
            
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                return data.get("result", [])
            except httpx.HTTPError as e:
                logger.error(f"❌ Ошибка связи с Telegram API: {e}")
                return []