"""Extend right_holder with legal/bank fields, restructure contract

Revision ID: f4a5b6c7d8e9
Revises: ae9e44f98dea
Create Date: 2026-09-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f4a5b6c7d8e9'
down_revision: Union[str, Sequence[str], None] = 'ae9e44f98dea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.drop_constraint('track_right_track_id_fkey', 'track_right', type_='foreignkey')
    
    # Создаем новое ограничение без ON DELETE CASCADE (по умолчанию NO ACTION)
    op.create_foreign_key(
        'track_right_track_id_fkey',
        'track_right',
        'track',
        ['track_id'],
        ['id']
    )



    # --- right_holder: новые юридические/финансовые поля ---
    op.add_column('right_holder', sa.Column('type', sa.String(length=20), nullable=True))
    op.add_column('right_holder', sa.Column('alias', sa.String(length=255), nullable=True))
    op.add_column('right_holder', sa.Column('email', sa.String(length=255), nullable=True))
    op.add_column('right_holder', sa.Column('phone', sa.String(length=50), nullable=True))
    op.add_column('right_holder', sa.Column('address', sa.Text(), nullable=True))
    op.add_column('right_holder', sa.Column('full_name', sa.String(length=255), nullable=True))
    op.add_column('right_holder', sa.Column('id_document_type', sa.String(length=50), nullable=True))
    op.add_column('right_holder', sa.Column('id_document_number', sa.String(length=50), nullable=True))
    op.add_column('right_holder', sa.Column('id_document_issued_by', sa.String(length=255), nullable=True))
    op.add_column('right_holder', sa.Column('id_document_issue_date', sa.Date(), nullable=True))
    op.add_column('right_holder', sa.Column('company_name', sa.String(length=255), nullable=True))
    op.add_column('right_holder', sa.Column('director_name', sa.String(length=255), nullable=True))
    op.add_column('right_holder', sa.Column('acting_basis', sa.String(length=255), nullable=True))
    op.add_column('right_holder', sa.Column('iin_bin', sa.String(length=20), nullable=True))
    op.add_column('right_holder', sa.Column('iban', sa.String(length=34), nullable=True))
    op.add_column('right_holder', sa.Column('bank_name', sa.String(length=255), nullable=True))
    op.add_column('right_holder', sa.Column('bik', sa.String(length=20), nullable=True))
    op.create_check_constraint(
        'right_holder_type_check', 'right_holder', "type IN ('INDIVIDUAL', 'COMPANY', 'IP')"
    )

    # --- contract: переименование + новые поля ---
    op.alter_column('contract', 'treaty_number', new_column_name='contract_number')
    op.alter_column('contract', 'effective_date', new_column_name='valid_from')
    op.alter_column('contract', 'termination_date', new_column_name='valid_to')
    op.drop_constraint('contract_treaty_number_key', 'contract', type_='unique')
    op.create_unique_constraint('contract_contract_number_key', 'contract', ['contract_number'])

    op.add_column('contract', sa.Column('signed_date', sa.Date(), nullable=True))
    op.add_column(
        'contract',
        sa.Column('status', sa.String(length=20), nullable=False, server_default=sa.text("'DRAFT'")),
    )
    op.add_column('contract', sa.Column('direction_type', sa.String(length=20), nullable=True))
    op.create_check_constraint(
        'contract_status_check', 'contract', "status IN ('DRAFT', 'ACTIVE', 'TERMINATED')"
    )
    op.create_check_constraint(
        'contract_direction_type_check', 'contract', "direction_type IN ('DIRECT_ARTIST', 'LABEL_CATALOG')"
    )

    # right_holder_id должен быть обязательным (у договора всегда один ПО)
    op.alter_column('contract', 'right_holder_id', existing_type=sa.Integer(), nullable=False)

    op.execute("UPDATE right_holder SET type = 'INDIVIDUAL' WHERE type IS NULL;")
    op.execute("UPDATE right_holder SET full_name  = name;")

def downgrade() -> None:

    op.drop_constraint('track_right_track_id_fkey', 'track_right', type_='foreignkey')
    
    op.create_foreign_key(
        'track_right_track_id_fkey',
        'track_right',
        'track',
        ['track_id'],
        ['id'],
        ondelete='CASCADE'
    )

    op.alter_column('contract', 'right_holder_id', existing_type=sa.Integer(), nullable=True)

    op.drop_constraint('contract_direction_type_check', 'contract', type_='check')
    op.drop_constraint('contract_status_check', 'contract', type_='check')
    op.drop_column('contract', 'direction_type')
    op.drop_column('contract', 'status')
    op.drop_column('contract', 'signed_date')

    op.drop_constraint('contract_contract_number_key', 'contract', type_='unique')
    op.create_unique_constraint('contract_treaty_number_key', 'contract', ['contract_number'])
    op.alter_column('contract', 'valid_to', new_column_name='termination_date')
    op.alter_column('contract', 'valid_from', new_column_name='effective_date')
    op.alter_column('contract', 'contract_number', new_column_name='treaty_number')

    op.drop_constraint('right_holder_type_check', 'right_holder', type_='check')
    op.drop_column('right_holder', 'bik')
    op.drop_column('right_holder', 'bank_name')
    op.drop_column('right_holder', 'iban')
    op.drop_column('right_holder', 'iin_bin')
    op.drop_column('right_holder', 'acting_basis')
    op.drop_column('right_holder', 'director_name')
    op.drop_column('right_holder', 'company_name')
    op.drop_column('right_holder', 'id_document_issue_date')
    op.drop_column('right_holder', 'id_document_issued_by')
    op.drop_column('right_holder', 'id_document_number')
    op.drop_column('right_holder', 'id_document_type')
    op.drop_column('right_holder', 'full_name')
    op.drop_column('right_holder', 'address')
    op.drop_column('right_holder', 'phone')
    op.drop_column('right_holder', 'email')
    op.drop_column('right_holder', 'alias')
    op.drop_column('right_holder', 'type')
