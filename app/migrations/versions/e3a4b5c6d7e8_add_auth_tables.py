"""Add auth tables (Role, User, RefreshToken, PasswordResetToken)

Revision ID: e3a4b5c6d7e8
Revises: d2b3c4e5f6a7
Create Date: 2026-08-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e3a4b5c6d7e8'
down_revision: Union[str, Sequence[str], None] = '9b7524fc29e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create role table
    op.create_table(
        'role',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id', name='role_pkey'),
        sa.UniqueConstraint('name', name='role_name_key')
    )

    # Create user table
    op.create_table(
        'user',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('is_verified', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('verification_token', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['role.id'], name='user_role_id_fkey', onupdate='CASCADE', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name='user_pkey'),
        sa.UniqueConstraint('email', name='user_email_key')
    )

    # Create refresh_token table
    op.create_table(
        'refresh_token',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('token', sa.String(length=500), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('device_info', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='refresh_token_user_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='refresh_token_pkey'),
        sa.UniqueConstraint('token', name='refresh_token_token_key')
    )

    # Create password_reset_token table
    op.create_table(
        'password_reset_token',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('token', sa.String(length=500), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='password_reset_token_user_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='password_reset_token_pkey'),
        sa.UniqueConstraint('token', name='password_reset_token_token_key')
    )

    # Insert default roles
    op.execute("""
        INSERT INTO role (name, description) VALUES
        ('USER', 'Default user role'),
        ('ADMIN', 'Administrator role')
    """)


def downgrade() -> None:
    op.drop_table('password_reset_token')
    op.drop_table('refresh_token')
    op.drop_table('user')
    op.drop_table('role')
