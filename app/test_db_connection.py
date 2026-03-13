#!/usr/bin/env python3
"""
Проверка соединения с БД и транзакций для Alembic
"""
import os
from sqlalchemy import create_engine, pool, text
from sqlalchemy.pool import NullPool

# URL БД
db_url = os.getenv("DATABASE_URL")
print(f"DATABASE_URL: {db_url}")

try:
    engine = create_engine(
        db_url,
        poolclass=NullPool
    )
    
    with engine.connect() as connection:
        print("✅ Подключение успешно")
        
        result = connection.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        ))
        tables = [row[0] for row in result]
        print(f"Существующие таблицы: {tables}")
        
        if 'alembic_version' in tables:
            result = connection.execute(text("SELECT version_num FROM alembic_version"))
            versions = result.fetchall()
            print(f"Версии в alembic_version: {versions}")
        else:
            print("Таблица alembic_version отсутствует - это хорошо для первой миграции")
            

        try:
            with connection.begin() as trans:
                connection.execute(text("""
                    CREATE TABLE test_transaction (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(100)
                    )
                """))
                print("✅ Тестовая таблица создана в транзакции")
                
                result = connection.execute(text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='test_transaction')"
                ))
                exists = result.scalar()
                print(f"✅ Таблица существует в транзакции: {exists}")
                
                trans.rollback()
            print("✅ Транзакция откатана - тестовая таблица удалена")
            
        except Exception as e:
            print(f"❌ Ошибка в транзакции: {e}")
            
except Exception as e:
    print(f"❌ Ошибка соединения: {e}")