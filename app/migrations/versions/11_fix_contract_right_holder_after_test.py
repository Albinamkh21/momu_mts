"""add_unknown_and_label_to_right_holder_type

Revision ID: <ваш_id>
Revises: <предыдущая_ревизия>
Create Date: 2026-03-30 ...
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '<ваш_id>'
down_revision = '<предыдущая_ревизия>'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Удаляем старое ограничение CheckConstraint

    # Удаляем возможные старые ограничения/индексы по name/inn
    op.execute("ALTER TABLE right_holder DROP CONSTRAINT IF EXISTS right_holder_name_key")
    op.execute("ALTER TABLE right_holder DROP CONSTRAINT IF EXISTS right_holder_name")
    op.execute("ALTER TABLE right_holder DROP CONSTRAINT IF EXISTS right_holder_inn_key")

    # Создаем новые частичные уникальные индексы
    op.create_index(
        'right_holder_iin_bin_idx',
        'right_holder',
        ['iin_bin'],
        unique=True,
        postgresql_where=sa.text('iin_bin IS NOT NULL')
    )
    op.create_index(
        'right_holder_name_no_iin_idx',
        'right_holder',
        ['name'],
        unique=True,
        postgresql_where=sa.text('iin_bin IS NULL')
    )

    op.drop_constraint('right_holder_type_check', 'right_holder', type_='check')
    
    # 2. Создаем новое ограничение с учетом UNKNOWN и LABEL
    op.create_check_constraint(
        'right_holder_type_check',
        'right_holder',
        "type IN ('INDIVIDUAL', 'COMPANY', 'IP', 'UNKNOWN', 'LABEL')"
    )
    
    # 3. Опционально: переводим старые пустые значения в UNKNOWN
    op.execute("UPDATE right_holder SET type = 'UNKNOWN' WHERE type IS NULL;")

    op.drop_constraint('contract_annex_contract_id_fkey', 'contract_annex', type_='foreignkey')
    op.create_foreign_key(
            'contract_annex_contract_id_fkey',
            'contract_annex',
            'contract',
            ['contract_id'],
            ['id'],
            ondelete='CASCADE'
        )

    # 2. Обновляем FK для строк приложений (contract_annex_items -> contract_annex)
    op.drop_constraint('contract_annex_items_annex_id_fkey', 'contract_annex_items', type_='foreignkey')
    op.create_foreign_key(
        'contract_annex_items_annex_id_fkey',
        'contract_annex_items',
        'contract_annex',
        ['annex_id'],
        ['id'],
        ondelete='CASCADE'
    )
    op.add_column('contract', sa.Column('file_path', sa.String(length=500), nullable=True))
    op.add_column('contract', sa.Column('file_name', sa.String(length=255), nullable=True))


def downgrade() -> None:

    op.drop_index('right_holder_name_no_iin_idx', table_name='right_holder')
    op.drop_index('right_holder_iin_bin_idx', table_name='right_holder')

    # Откат миграции назад (если потребуется)
    op.drop_constraint('right_holder_type_check', 'right_holder', type_='check')
    op.create_check_constraint(
        'right_holder_type_check',
        'right_holder',
        "type IN ('INDIVIDUAL', 'COMPANY', 'IP')"
    )
    op.execute("UPDATE right_holder SET type = NULL WHERE type = 'UNKNOWN';")

    op.drop_constraint('contract_annex_items_annex_id_fkey', 'contract_annex_items', type_='foreignkey')
    op.create_foreign_key(
        'contract_annex_items_annex_id_fkey',
        'contract_annex_items',
        'contract_annex',
        ['annex_id'],
        ['id']
    )

    op.drop_constraint('contract_annex_contract_id_fkey', 'contract_annex', type_='foreignkey')
    op.create_foreign_key(
        'contract_annex_contract_id_fkey',
        'contract_annex',
        'contract',
        ['contract_id'],
        ['id']
    )
    op.drop_column('contract', 'file_path')
    op.drop_column('contract', 'file_name')