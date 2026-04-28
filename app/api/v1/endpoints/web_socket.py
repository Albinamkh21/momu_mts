from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import json
from redis import asyncio as aioredis
from services.broadcaster import TaskProgress 

router = APIRouter()

@router.websocket("/task/{task_id}")
async def task_status_websocket(websocket: WebSocket, task_id: str):
    await websocket.accept()
    # Получаем синхронный клиент Redis из вашего TaskProgress (или создадим асинхронный)
    # Но TaskProgress у вас использует синхронный redis, а для pub/sub в асинхронном цикле лучше использовать асинхронный клиент.
    # Рекомендую создать отдельный асинхронный клиент.
    redis_url = "redis://momu_redis:6379/0"  # или из переменных окружения
    pubsub = None
    try:
        # Асинхронный Redis клиент
        redis_client = await aioredis.from_url(redis_url, decode_responses=True)
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(f"task_progress_{task_id}")
        
        # Цикл получения сообщений
        while True:
            # Ждём следующее сообщение (не блокирует)
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                data = message['data']
                await websocket.send_text(data)
            # Небольшая задержка, чтобы не грузить процессор
            await asyncio.sleep(0.01)
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for task {task_id}")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        if pubsub:
            await pubsub.unsubscribe(f"task_progress_{task_id}")
            await pubsub.close()
        if redis_client:
            await redis_client.close()
        await websocket.close()