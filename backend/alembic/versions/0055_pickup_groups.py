"""Groupe d'interception (*8) nomme -- entite organisationnelle qui permet de
creer un groupe vide puis d'y assigner des postes, au lieu de taper le meme
nom de groupe en texte libre sur chaque poste (demande Philippe 2026-08-07,
meme principe que les groupes d'appel). Le dialplan (*8) continue de matcher
par SIPExtension.pickup_group (string) -- non touche par cette migration.

Revision ID: 0055_pickup_groups
Revises: 0054_schedule_rule_destination
Create Date: 2026-08-07
"""
from typing import Union, Sequence
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = '0055_pickup_groups'
down_revision: Union[str, Sequence[str], None] = '0054_schedule_rule_destination'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'pickup_groups',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('pickup_groups')
