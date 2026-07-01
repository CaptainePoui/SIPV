"""add cdr and rate_prefixes tables

Revision ID: 0006_cdr
Revises: 0005_voicemail
Create Date: 2026-06-29

"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0006_cdr'
down_revision: Union[str, Sequence[str], None] = '0005_voicemail'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'rate_prefixes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('prefix', sa.String(20), nullable=False),
        sa.Column('description', sa.String(100), nullable=True),
        sa.Column('country', sa.String(60), nullable=True),
        sa.Column('region', sa.String(60), nullable=True),
        sa.Column('rate_per_minute', sa.Numeric(10, 6), nullable=False),
        sa.Column('min_duration', sa.Integer(), nullable=False, server_default='6'),
        sa.Column('increment', sa.Integer(), nullable=False, server_default='6'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('prefix'),
    )

    op.create_table(
        'cdr',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('accountcode', sa.String(20), nullable=True),
        sa.Column('src', sa.String(80), nullable=True),
        sa.Column('dst', sa.String(80), nullable=True),
        sa.Column('dcontext', sa.String(80), nullable=True),
        sa.Column('clid', sa.String(80), nullable=True),
        sa.Column('channel', sa.String(80), nullable=True),
        sa.Column('dstchannel', sa.String(80), nullable=True),
        sa.Column('lastapp', sa.String(80), nullable=True),
        sa.Column('lastdata', sa.String(80), nullable=True),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('answer_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('billsec', sa.Integer(), nullable=True),
        sa.Column('disposition', sa.String(45), nullable=True),
        sa.Column('amaflags', sa.Integer(), nullable=True),
        sa.Column('userfield', sa.String(255), nullable=True),
        sa.Column('uniqueid', sa.String(150), nullable=True),
        sa.Column('linkedid', sa.String(150), nullable=True),
        sa.Column('sequence', sa.Integer(), nullable=True),
        sa.Column('direction', sa.String(10), nullable=True),
        sa.Column('prefix_id', sa.UUID(), nullable=True),
        sa.Column('cost', sa.Numeric(10, 6), nullable=True),
        sa.Column('rate_per_minute', sa.Numeric(10, 6), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['prefix_id'], ['rate_prefixes.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_cdr_tenant_id', 'cdr', ['tenant_id'])
    op.create_index('ix_cdr_start_time', 'cdr', ['start_time'])
    op.create_index('ix_cdr_src', 'cdr', ['src'])
    op.create_index('ix_cdr_dst', 'cdr', ['dst'])


def downgrade() -> None:
    op.drop_index('ix_cdr_dst', table_name='cdr')
    op.drop_index('ix_cdr_src', table_name='cdr')
    op.drop_index('ix_cdr_start_time', table_name='cdr')
    op.drop_index('ix_cdr_tenant_id', table_name='cdr')
    op.drop_table('cdr')
    op.drop_table('rate_prefixes')
