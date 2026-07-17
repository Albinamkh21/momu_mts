"""Add track_id to ui_track_drafts for edit-mode drafts

Revision ID: d2b3c4e5f6a7
Revises: c1a2b3d4e5f6
Create Date: 2026-07-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd2b3c4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'c1a2b3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Создаем расширение pg_trgm, если его еще нет (нужно для GIN trgm индекса)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # 2. Создаем первый индекс (обычный GIN)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_person_name_trgm 
        ON person 
        USING gin(full_name gin_trgm_ops);
    """)

    # 3. Создаем второй индекс (CONCURRENTLY)
    # Для этого временно отключаем транзакционность внутри блока выполнения
    with op.get_context().autocommit_block():
        op.execute("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tc_person_role 
            ON track_contribution(person_id, role);
        """)


def downgrade() -> None:
    # Удаляем индексы в обратном порядке
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_tc_person_role;")
    
    op.execute("DROP INDEX IF EXISTS idx_person_name_trgm;")
