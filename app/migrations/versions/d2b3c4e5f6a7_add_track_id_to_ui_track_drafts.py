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
    op.add_column('ui_track_drafts', sa.Column('track_id', sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        'ui_track_drafts_track_id_fkey', 'ui_track_drafts', 'track', ['track_id'], ['id'], ondelete='CASCADE'
    )


def downgrade() -> None:
    op.drop_constraint('ui_track_drafts_track_id_fkey', 'ui_track_drafts', type_='foreignkey')
    op.drop_column('ui_track_drafts', 'track_id')
