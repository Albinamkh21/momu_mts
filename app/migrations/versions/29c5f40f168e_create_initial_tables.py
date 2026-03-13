"""create_initial_tables

Revision ID: 29c5f40f168e
Revises: 
Create Date: 2026-03-04 12:05:54.040319

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '29c5f40f168e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    print("=== Начинаем создание таблиц ===")
    
    print("Creating copyright_holders table...")
    op.create_table(
        'copyright_holders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index('ix_copyright_holders_name', 'copyright_holders', ['name'])
    print("✅ Table copyright_holders created")
    
    print("Creating tracks table...")
    op.create_table(
        'tracks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('isrc', sa.String(12), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('artist', sa.String(500), nullable=True),
        sa.Column('authors', sa.String(1000), nullable=True),
        sa.Column('composer', sa.String(500), nullable=True),
        sa.Column('lyricist', sa.String(500), nullable=True),
        sa.Column('album_name', sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('isrc')
    )
    op.create_index('ix_tracks_isrc', 'tracks', ['isrc'])
    op.create_index('ix_tracks_title', 'tracks', ['title'])
    print("✅ Table tracks created")
    
    print("Creating catalog table...")
    op.create_table(
        'catalog',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('holder_id', sa.Integer(), nullable=False),
        sa.Column('track_id', sa.Integer(), nullable=False),
        sa.Column('authors_rights', sa.Float(), nullable=False, default=0.0),
        sa.Column('related_rights', sa.Float(), nullable=False, default=0.0),
        sa.ForeignKeyConstraint(['holder_id'], ['copyright_holders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['track_id'], ['tracks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_catalog_holder_id', 'catalog', ['holder_id'])
    op.create_index('ix_catalog_track_id', 'catalog', ['track_id'])
    print("✅ Table catalog created")
    
    print("=== Все таблицы успешно созданы ===")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_catalog_track_id', 'catalog')
    op.drop_index('ix_catalog_holder_id', 'catalog')
    op.drop_table('catalog')
    
    op.drop_index('ix_tracks_title', 'tracks')
    op.drop_index('ix_tracks_isrc', 'tracks')
    op.drop_table('tracks')
    
    op.drop_index('ix_copyright_holders_name', 'copyright_holders')
    op.drop_table('copyright_holders')
