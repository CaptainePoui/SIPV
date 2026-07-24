"""TASK-S018.5 -- plan d'appel reellement applique (Canada/US/intl/premium/PIN/limite)

Revision ID: 0029_call_permission_s018_5
Revises: 0028_record_categories
Create Date: 2026-07-24
"""
from typing import Union, Sequence
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = '0029_call_permission_s018_5'
down_revision: Union[str, Sequence[str], None] = '0028_record_categories'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sip_extensions', sa.Column('allow_canada', sa.Boolean(), nullable=True))
    op.add_column('sip_extensions', sa.Column('allow_us', sa.Boolean(), nullable=True))
    op.add_column('sip_extensions', sa.Column('allow_international', sa.Boolean(), nullable=True))
    op.add_column('sip_extensions', sa.Column('allow_premium', sa.Boolean(), nullable=True))
    op.add_column('sip_extensions', sa.Column('blocked_countries', sa.String(255), nullable=True))
    op.add_column('sip_extensions', sa.Column('blocked_prefixes', sa.String(255), nullable=True))
    op.add_column('sip_extensions', sa.Column('ld_pin', sa.String(255), nullable=True))
    op.add_column('sip_extensions', sa.Column('ld_monthly_limit', sa.Numeric(10, 2), nullable=True))
    op.add_column('sip_extensions', sa.Column('preferred_trunk_id', UUID(as_uuid=True), sa.ForeignKey('sip_trunks.id', ondelete='SET NULL'), nullable=True))

    op.add_column('tenants', sa.Column('default_allow_canada', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('tenants', sa.Column('default_allow_us', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('tenants', sa.Column('default_allow_international', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('tenants', sa.Column('default_allow_premium', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('tenants', sa.Column('default_blocked_countries', sa.String(255), nullable=True))
    op.add_column('tenants', sa.Column('default_blocked_prefixes', sa.String(255), nullable=True))
    op.add_column('tenants', sa.Column('default_ld_pin', sa.String(255), nullable=True))
    op.add_column('tenants', sa.Column('default_ld_monthly_limit', sa.Numeric(10, 2), nullable=True))


def downgrade() -> None:
    op.drop_column('tenants', 'default_ld_monthly_limit')
    op.drop_column('tenants', 'default_ld_pin')
    op.drop_column('tenants', 'default_blocked_prefixes')
    op.drop_column('tenants', 'default_blocked_countries')
    op.drop_column('tenants', 'default_allow_premium')
    op.drop_column('tenants', 'default_allow_international')
    op.drop_column('tenants', 'default_allow_us')
    op.drop_column('tenants', 'default_allow_canada')

    op.drop_column('sip_extensions', 'preferred_trunk_id')
    op.drop_column('sip_extensions', 'ld_monthly_limit')
    op.drop_column('sip_extensions', 'ld_pin')
    op.drop_column('sip_extensions', 'blocked_prefixes')
    op.drop_column('sip_extensions', 'blocked_countries')
    op.drop_column('sip_extensions', 'allow_premium')
    op.drop_column('sip_extensions', 'allow_international')
    op.drop_column('sip_extensions', 'allow_us')
    op.drop_column('sip_extensions', 'allow_canada')
