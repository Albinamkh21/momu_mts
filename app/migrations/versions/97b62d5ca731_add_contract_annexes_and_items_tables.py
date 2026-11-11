"""add contract annexes and items tables

Revision ID: 97b62d5ca731
Revises: a1b2c3d4e5f6
Create Date: 2026-11-11 12:22:58.062977

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '97b62d5ca731'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Создаем ENUM тип annex_status_enum
    annex_status_enum = postgresql.ENUM(
        'DRAFT', 'PROCESSING', 'COMPLETED', 'FAILED',
        name='annex_status_enum'
    )
    

    # 2. Создаем таблицу contract_annex
    op.create_table(
        'contract_annex',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('contract_id', sa.BigInteger(), sa.ForeignKey('contract.id', ondelete='CASCADE'), nullable=False),
        sa.Column('annex_number', sa.String(length=50), nullable=False),
        sa.Column('doc_date', sa.Date(), nullable=False),
        sa.Column('status', annex_status_enum, nullable=False),
        sa.Column('payload_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('contract_id', 'annex_number', name='uq_contract_annex_number'),
    )
    op.create_index(op.f('ix_contract_annex_contract_id'), 'contract_annex', ['contract_id'], unique=False)

    # 3. Создаем таблицу contract_annex_items
    op.create_table(
        'contract_annex_items',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('annex_id', sa.BigInteger(), sa.ForeignKey('contract_annex.id', ondelete='CASCADE'), nullable=False),
        sa.Column('line_number', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=100), nullable=True),
        sa.Column('track_title', sa.String(length=255), nullable=False),
        sa.Column('artist_name', sa.String(length=255), nullable=False),
        sa.Column('related_rights_percent', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('composer_name', sa.String(length=255), nullable=False),
        sa.Column('composer_percent', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('lyricist_name', sa.String(length=255), nullable=False),
        sa.Column('lyricist_percent', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('track_id', sa.BigInteger(), sa.ForeignKey('track.id', ondelete='SET NULL'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_contract_annex_items_annex_id'), 'contract_annex_items', ['annex_id'], unique=False)
    op.create_index(op.f('ix_contract_annex_items_track_id'), 'contract_annex_items', ['track_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_contract_annex_items_track_id'), table_name='contract_annex_items')
    op.drop_index(op.f('ix_contract_annex_items_annex_id'), table_name='contract_annex_items')
    op.drop_table('contract_annex_items')

    op.drop_index(op.f('ix_contract_annex_contract_id'), table_name='contract_annex')
    op.drop_table('contract_annex')

    annex_status_enum = postgresql.ENUM(
        'DRAFT', 'PROCESSING', 'COMPLETED', 'FAILED',
        name='annex_status_enum'
    )
    annex_status_enum.drop(op.get_bind(), checkfirst=True)
