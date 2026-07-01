"""add phone_models and provisioned_phones tables

Revision ID: 0008_provisioning
Revises: 0007_e911
Create Date: 2026-06-29

"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0008_provisioning'
down_revision: Union[str, Sequence[str], None] = '0007_e911'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'phone_models',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('brand', sa.String(40), nullable=False),
        sa.Column('model', sa.String(60), nullable=False),
        sa.Column('firmware_version', sa.String(30), nullable=True),
        sa.Column('max_accounts', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('provisioning_protocol', sa.String(20), nullable=False, server_default='http'),
        sa.Column('config_template', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'provisioned_phones',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('extension_id', sa.UUID(), nullable=True),
        sa.Column('phone_model_id', sa.UUID(), nullable=True),
        sa.Column('mac_address', sa.String(17), nullable=False),
        sa.Column('display_name', sa.String(60), nullable=True),
        sa.Column('location', sa.String(100), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('firmware_version', sa.String(30), nullable=True),
        sa.Column('last_provisioned', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=True),
        sa.Column('extra_config', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['extension_id'], ['sip_extensions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['phone_model_id'], ['phone_models.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('mac_address'),
    )


def downgrade() -> None:
    op.drop_table('provisioned_phones')
    op.drop_table('phone_models')
