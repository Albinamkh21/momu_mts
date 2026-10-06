"""add catalog tables and staging diff

Revision ID: a1b2c3d4e5f6
Revises: f4a5b6c7d8e9
Create Date: 2026-10-05 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f4a5b6c7d8e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Создаем ENUM тип common_status
    common_status_enum = postgresql.ENUM(
        'new', 'committed', 'deleted', 'inserted', 'existing', 'updated', 
        name='common_status'
    )
    common_status_enum.create(op.get_bind(), checkfirst=True)

    # 2. Создаем таблицу staging_track_diff
    op.create_table(
        'staging_track_diff',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('track_id', sa.BigInteger(), nullable=True),
        sa.Column('track_name', sa.Text(), nullable=True),
        sa.Column('upload_id', sa.String(length=255), nullable=True),
        sa.Column('field_name', sa.String(length=255), nullable=True),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='public'
    )

    # 3. Создаем таблицу catalog_upload
    op.create_table(
        'catalog_upload',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('upload_id', sa.Text(), nullable=False),
        sa.Column('label_id', sa.Integer(), sa.ForeignKey('label.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('filename', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='PROCESSING', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('upload_id', name='uq_catalog_upload_upload_id')
    )

    # 4. Обновляем таблицу staging_catalog_v2
    op.add_column('staging_catalog_v2', sa.Column('status', common_status_enum, server_default='new', nullable=True))
    op.add_column('staging_catalog_v2', sa.Column('track_id', sa.BigInteger(), nullable=True))
    
    # Меняем тип колонки user_id с использованием USING
    op.execute("ALTER TABLE staging_catalog_v2 ALTER COLUMN user_id TYPE INTEGER USING user_id::integer;")


    # Добавление колонок
    op.add_column('track', sa.Column('isDeleted', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('track', sa.Column('deleted_at', sa.TIMESTAMP(timezone=True), nullable=True))
    
    # Создание частичного индекса
    op.create_index(
        'idx_track_is_deleted',
        'track',
        ['isDeleted'],
        unique=False,
        postgresql_where=sa.text('isDeleted = false')
    )

    # 5. Создаем индексы
    op.create_index(
        'idx_staging_catalog_v2_isrc_right_id', 
        'staging_catalog_v2', 
        ['isrc', 'right_id']
    )
    
    op.create_index(
        'idx_ui_track_drafts_track_id', 
        'ui_track_drafts', 
        ['track_id']
    )


def downgrade() -> None:
    # 1. Удаляем индексы
    op.execute('DROP INDEX IF EXISTS idx_ui_track_drafts_track_id;')
    op.drop_index('idx_staging_catalog_v2_isrc_right_id', table_name='staging_catalog_v2')

    # 2. Откатываем изменения в staging_catalog_v2
    # Предполагаем, что user_id ранее был строкой (VARCHAR). Если был другим (например, TEXT), замени 'VARCHAR' на 'TEXT'
    op.execute("ALTER TABLE staging_catalog_v2 ALTER COLUMN user_id TYPE VARCHAR USING user_id::varchar;")
    op.drop_column('staging_catalog_v2', 'track_id')
    op.drop_column('staging_catalog_v2', 'status')

    # 3. Удаляем таблицы
    op.drop_table('catalog_upload')
    op.drop_table('staging_track_diff', schema='public')

    # 4. Удаляем ENUM
    common_status_enum = postgresql.ENUM(
        'new', 'committed', 'deleted', 'inserted', 'existing', 'updated', 
        name='common_status'
    )
    common_status_enum.drop(op.get_bind(), checkfirst=True)

    op.drop_index('idx_track_is_deleted', table_name='track', postgresql_where=sa.text('isDeleted = false'))
    op.drop_column('track', 'deleted_at')
    op.drop_column('track', 'isDeleted')