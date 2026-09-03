"""clean_types

Revision ID: ae9e44f98dea
Revises: e3a4b5c6d7e8
Create Date: 2026-09-02 16:09:46.905916

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ae9e44f98dea'
down_revision: Union[str, Sequence[str], None] = 'e3a4b5c6d7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # 1. Обновляем внешний ключ для report.partner_id (удаляем ondelete='CASCADE')
    op.drop_constraint('report_partner_id_fkey', 'report', type_='foreignkey')
    op.create_foreign_key('report_partner_id_fkey', 'report', 'partners', ['partner_id'], ['id'])

    op.drop_constraint('track_label_label_id_fkey', 'track_label', type_='foreignkey')
    op.create_foreign_key(
        'track_label_label_id_fkey',
        'track_label',
        'label',
        ['label_id'],
        ['id'],
        ondelete='RESTRICT'
    )


    # 2. Изменяем типы колонок в report_track_rights_distribution с BigInteger на Integer
    op.alter_column('report_track_rights_distribution', 'id',
               existing_type=sa.BigInteger(),
               type_=sa.Integer(),
               existing_nullable=False,
               autoincrement=True)
    op.alter_column('report_track_rights_distribution', 'report_id',
               existing_type=sa.BigInteger(),
               type_=sa.Integer(),
               existing_nullable=False)
    op.alter_column('report_track_rights_distribution', 'track_id',
               existing_type=sa.BigInteger(),
               type_=sa.Integer(),
               existing_nullable=False)
    op.alter_column('report_track_rights_distribution', 'right_holder_id',
               existing_type=sa.BigInteger(),
               type_=sa.Integer(),
               existing_nullable=False)

    # 3. Добавляем внешние ключи для report_track_rights_distribution
    op.create_foreign_key('fk_rtrd_report_id', 'report_track_rights_distribution', 'report', ['report_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_rtrd_staging_id', 'report_track_rights_distribution', 'staging_report_agg', ['staging_id'], ['id'])
    op.create_foreign_key('fk_rtrd_track_id', 'report_track_rights_distribution', 'track', ['track_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_rtrd_right_holder_id', 'report_track_rights_distribution', 'right_holder', ['right_holder_id'], ['id'])
    op.create_foreign_key('fk_rtrd_right_category_id', 'report_track_rights_distribution', 'right_category', ['right_category_id'], ['id'])
    op.create_foreign_key('fk_rtrd_right_usage_type_id', 'report_track_rights_distribution', 'right_usage_type', ['right_usage_type_id'], ['id'])

    # 4. Добавляем индексы для report_track_rights_distribution
    op.create_index('idx_rtrd_report_id', 'report_track_rights_distribution', ['report_id'])
    op.create_index('idx_rtrd_track_id', 'report_track_rights_distribution', ['track_id'])


def downgrade():
    # Откат индексов
    op.drop_index('idx_rtrd_track_id', table_name='report_track_rights_distribution')
    op.drop_index('idx_rtrd_report_id', table_name='report_track_rights_distribution')

    # Откат внешних ключей report_track_rights_distribution
    op.drop_constraint('fk_rtrd_right_usage_type_id', 'report_track_rights_distribution', type_='foreignkey')
    op.drop_constraint('fk_rtrd_right_category_id', 'report_track_rights_distribution', type_='foreignkey')
    op.drop_constraint('fk_rtrd_right_holder_id', 'report_track_rights_distribution', type_='foreignkey')
    op.drop_constraint('fk_rtrd_track_id', 'report_track_rights_distribution', type_='foreignkey')
    op.drop_constraint('fk_rtrd_staging_id', 'report_track_rights_distribution', type_='foreignkey')
    op.drop_constraint('fk_rtrd_report_id', 'report_track_rights_distribution', type_='foreignkey')

    # Возврат типов BigInteger в report_track_rights_distribution
    op.alter_column('report_track_rights_distribution', 'right_holder_id',
               existing_type=sa.Integer(),
               type_=sa.BigInteger(),
               existing_nullable=False)
    op.alter_column('report_track_rights_distribution', 'track_id',
               existing_type=sa.Integer(),
               type_=sa.BigInteger(),
               existing_nullable=False)
    op.alter_column('report_track_rights_distribution', 'report_id',
               existing_type=sa.Integer(),
               type_=sa.BigInteger(),
               existing_nullable=False)
    op.alter_column('report_track_rights_distribution', 'id',
               existing_type=sa.Integer(),
               type_=sa.BigInteger(),
               existing_nullable=False,
               autoincrement=True)

    # Возврат старого внешнего ключа для report.partner_id с ondelete='CASCADE'
    op.drop_constraint('report_partner_id_fkey', 'report', type_='foreignkey')
    op.create_foreign_key('report_partner_id_fkey', 'report', 'partners', ['partner_id'], ['id'], ondelete='CASCADE')
