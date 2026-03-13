#!/usr/bin/env python3
"""
Проверка подключения к БД и состояния схемы
"""
import os
from sqlalchemy import create_engine, text

db_url = os.getenv("DATABASE_URL")
print(f"DATABASE_URL: {db_url}")

if not db_url:
    print("❌ DATABASE_URL не установлена!")
    exit(1)

try:
    engine = create_engine(db_url)
    with engine.connect() as conn:
        print("✅ Подключение к БД успешно")
        
        result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))
        tables = [row[0] for row in result]
        print(f"Таблицы в БД: {tables}")
        
        if 'alembic_version' in tables:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            version = result.fetchone()
            if version:
                print(f"Текущая версия Alembic: {version[0]}")
            else:
                print("Таблица alembic_version пуста")
        else:
            print("Таблица alembic_version отсутствует")
            
except Exception as e:
    print(f"❌ Ошибка подключения к БД: {e}")