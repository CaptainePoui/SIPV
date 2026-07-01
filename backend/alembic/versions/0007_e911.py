"""add e911_addresses and did_911_assignments tables

Revision ID: 0007_e911
Revises: 0006_cdr
Create Date: 2026-06-29

"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0007_e911'
down_revision: Union[str, Sequence[str], None] = '0006_cdr'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'e911_addresses',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('label', sa.String(100), nullable=False),
        sa.Column('civic_number', sa.String(20), nullable=False),
        sa.Column('street_name', sa.String(100), nullable=False),
        sa.Column('unit', sa.String(20), nullable=True),
        sa.Column('city', sa.String(60), nullable=False),
        sa.Column('province', sa.String(2), nullable=False),
        sa.Column('postal_code', sa.String(10), nullable=False),
        sa.Column('country', sa.String(2), nullable=False, server_default='CA'),
        sa.Column('is_validated', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('carrier_reference', sa.String(100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'did_911_assignments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('did_id', sa.UUID(), nullable=False),
        sa.Column('e911_address_id', sa.UUID(), nullable=False),
        sa.Column('emergency_trunk_id', sa.UUID(), nullable=True),
        sa.Column('alert_email', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['did_id'], ['tenant_dids.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['e911_address_id'], ['e911_addresses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['emergency_trunk_id'], ['sip_trunks.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('did_id'),
    )


def downgrade() -> None:
    op.drop_table('did_911_assignments')
    op.drop_table('e911_addresses')
