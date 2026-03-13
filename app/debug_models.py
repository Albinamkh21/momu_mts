#!/usr/bin/env python3
"""
Диагностический скрипт для проверки импорта моделей
"""
import sys
import os

print(f"Python path: {sys.path}")
print(f"Current dir: {os.getcwd()}")

try:
    from core.database import Base
    print(f"✅ Base imported successfully: {Base}")
except Exception as e:
    print(f"❌ Error importing Base: {e}")

try:
    from models.track import Track
    print(f"✅ Track imported successfully: {Track}")
except Exception as e:
    print(f"❌ Error importing Track: {e}")

try:
    from models.copyright_holder import CopyrightHolder
    print(f"✅ CopyrightHolder imported successfully: {CopyrightHolder}")
except Exception as e:
    print(f"❌ Error importing CopyrightHolder: {e}")

try:
    from models.catalog import Catalog
    print(f"✅ Catalog imported successfully: {Catalog}")
except Exception as e:
    print(f"❌ Error importing Catalog: {e}")

try:
    from models import Base as ModelsBase
    print(f"✅ Base from models imported successfully: {ModelsBase}")
    print(f"Tables in metadata: {list(ModelsBase.metadata.tables.keys())}")
    
    if ModelsBase.metadata.tables:
        for table_name, table in ModelsBase.metadata.tables.items():
            print(f"Table {table_name}:")
            for column in table.columns:
                print(f"  - {column.name}: {column.type}")
    else:
        print("❌ No tables found in metadata!")
        
except Exception as e:
    print(f"❌ Error importing from models: {e}")