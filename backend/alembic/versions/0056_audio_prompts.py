"""TASK-S046/S047 : bibliotheque de phrases/annonces reutilisables (AudioPrompt)
par tenant, + champs de chainage "apres le message" sur TenantDID et
InboundRoute (demande Philippe 2026-08-07 : raccroche par defaut apres avoir
joue le message, "Ajouter une destination" permet de chainer vers une 2e
destination cote UI).

Revision ID: 0056_audio_prompts
Revises: 0055_pickup_groups
Create Date: 2026-08-07
"""
from typing import Union, Sequence
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = '0056_audio_prompts'
down_revision: Union[str, Sequence[str], None] = '0055_pickup_groups'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'audio_prompts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('duration_seconds', sa.Integer, nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.add_column('tenant_dids', sa.Column('after_message_destination_type', sa.String(20), nullable=True))
    op.add_column('tenant_dids', sa.Column('after_message_destination', sa.String(100), nullable=True))
    op.add_column('inbound_routes', sa.Column('after_message_destination_type', sa.String(20), nullable=True))
    op.add_column('inbound_routes', sa.Column('after_message_destination', sa.String(100), nullable=True))
    op.add_column('ivrs', sa.Column('greeting_prompt_id', UUID(as_uuid=True), sa.ForeignKey('audio_prompts.id', ondelete='SET NULL'), nullable=True))


def downgrade() -> None:
    op.drop_column('ivrs', 'greeting_prompt_id')
    op.drop_column('inbound_routes', 'after_message_destination')
    op.drop_column('inbound_routes', 'after_message_destination_type')
    op.drop_column('tenant_dids', 'after_message_destination')
    op.drop_column('tenant_dids', 'after_message_destination_type')
    op.drop_table('audio_prompts')
