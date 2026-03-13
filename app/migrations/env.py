import sys
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, create_engine, text
from sqlalchemy import pool

from alembic import context

current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.join(current_dir, '..')
sys.path.insert(0, project_dir)

from models import Base
from models.track import Track
from models.copyright_holder import CopyrightHolder 
from models.catalog import Catalog

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# DEBUG: Проверяем какие таблицы видит Alembic
print(f"DEBUG: Найдены таблицы: {list(target_metadata.tables.keys())}")
print(f"DEBUG: Загруженные модели: Track={Track}, CopyrightHolder={CopyrightHolder}, Catalog={Catalog}")


# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        raise RuntimeError("DATABASE_URL environment variable is not set")

    print(f"DEBUG: Connecting to: {db_url}")
    print(f"DEBUG: Target metadata tables: {list(target_metadata.tables.keys())}")
    
    for table_name, table in target_metadata.tables.items():
        print(f"DEBUG: Table {table_name} columns: {[c.name for c in table.columns]}")

    connectable = create_engine(
        db_url,
        poolclass=pool.NullPool,
        isolation_level="READ_COMMITTED"
    )

    with connectable.connect() as connection:
        print(f"DEBUG: Connected to database successfully")
        
        try:
            result = connection.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
            )
            existing_tables = [row[0] for row in result]
            print(f"DEBUG: Existing tables in DB: {existing_tables}")
        except Exception as e:
            print(f"DEBUG: Error checking existing tables: {e}")
        
        from alembic.autogenerate import compare_metadata
        from alembic.migration import MigrationContext
        
        migration_context = MigrationContext.configure(connection)
        diff = compare_metadata(migration_context, target_metadata)
        print(f"DEBUG: Alembic diff result: {diff}")
        
        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_as_batch=False
        )

        with context.begin_transaction():
            context.run_migrations()
