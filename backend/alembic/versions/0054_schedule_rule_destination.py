"""Destination par plage horaire (ScheduleRule) -- Philippe veut pouvoir
router chaque plage vers une destination differente (ex: 8h-10h -> IVR 001,
10h15-12h -> messagerie 201, 12h-13h -> ring group cafeteria) au lieu d'une
seule destination "ferme" globale (TASK-S045.1, demande 2026-08-07).

Revision ID: 0054_schedule_rule_destination
Revises: 0053_tenant_did_schedule_id
Create Date: 2026-08-07
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0054_schedule_rule_destination'
down_revision: Union[str, Sequence[str], None] = '0053_tenant_did_schedule_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('schedule_rules', sa.Column('destination_type', sa.String(20), nullable=True))
    op.add_column('schedule_rules', sa.Column('destination', sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column('schedule_rules', 'destination')
    op.drop_column('schedule_rules', 'destination_type')
