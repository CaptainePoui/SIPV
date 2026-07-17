"""audit_log table

Revision ID: 0015_audit_log
Revises: 0014_schedules
Create Date: 2026-07-09
"""
from typing import Union, Sequence
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from alembic import op

revision: str = '0015_audit_log'
down_revision: Union[str, Sequence[str], None] = '0014_schedules'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'audit_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='SET NULL'), nullable=True),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', sa.String(36), nullable=True),
        sa.Column('entity_label', sa.String(200), nullable=True),
        sa.Column('action', sa.String(20), nullable=False),
        sa.Column('old_data', JSONB, nullable=True),
        sa.Column('new_data', JSONB, nullable=True),
        sa.Column('changed_by', sa.String(255), nullable=False),
        sa.Column('changed_by_ip', sa.String(45), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_audit_logs_tenant_id', 'audit_logs', ['tenant_id'])
    op.create_index('ix_audit_logs_entity_type', 'audit_logs', ['entity_type'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])
    op.create_index('ix_audit_logs_changed_by', 'audit_logs', ['changed_by'])


def downgrade() -> None:
    op.drop_table('audit_logs')
