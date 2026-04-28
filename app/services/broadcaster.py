import os
import redis
import json
from datetime import datetime



REDIS_URL = os.getenv("REDIS_URL", "redis://momu_redis:6379/0")

class TaskProgress:
    _redis_instance = None

    @classmethod
    def _get_client(cls):
   
        if cls._redis_instance is None:
         
            cls._redis_instance = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        return cls._redis_instance

    @classmethod
    def emit(cls, task_id: str, message: str, level: str = "info"):

        if not task_id:
            return

        payload = {
            "task_id": task_id,
            "message": message,
            "level": level,  # 'info', 'success', 'error'
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            client = cls._get_client()
            client.publish(f"task_progress_{task_id}", json.dumps(payload))
            client.rpush(f"task_history_{task_id}", json.dumps(payload))
            client.expire(f"task_history_{task_id}", 3600)
        except Exception as e:
          
            print(f"🔴 Broadcaster Error: {e}")