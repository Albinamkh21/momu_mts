import os
from sqlalchemy import create_engine
from core.database import Base
from models.track import Track
from models.copyright_holder import CopyrightHolder
from models.catalog import Catalog

DATABASE_URL = os.getenv("DATABASE_URL")
print(f"Попытка подключения к: {DATABASE_URL}")

try:
    sync_url = DATABASE_URL.replace("+asyncpg", "+psycopg2")
    engine = create_engine(sync_url)
    
    Base.metadata.create_all(bind=engine)
    print("✅ Таблицы успешно созданы в базе!")
    
    print(f"Зарегистрировано таблиц: {list(Base.metadata.tables.keys())}")

except Exception as e:
    print(f"❌ Ошибка при создании: {e}")