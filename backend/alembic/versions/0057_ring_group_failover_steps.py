"""TASK-S051 : chaine de destinations de secours (illimitee) pour un groupe
d'appel sans reponse -- remplace RingGroup.no_answer_destination, jamais
reellement cable dans le dialplan (bug), par une liste ordonnee.

Revision ID: 0057_ring_group_failover_steps
Revises: 0056_audio_prompts
Create Date: 2026-08-07
"""
from typing import Union, Sequence
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = '0057_ring_group_failover_steps'
down_revision: Union[str, Sequence[str], None] = '0056_audio_prompts'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ring_group_failover_steps',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('ring_group_id', UUID(as_uuid=True), sa.ForeignKey('ring_groups.id', ondelete='CASCADE'), nullable=False),
        sa.Column('step_order', sa.Integer, nullable=False, server_default='0'),
        sa.Column('destination_type', sa.String(20), nullable=False),
        sa.Column('destination', sa.String(100), nullable=False),
        sa.Column('ring_seconds', sa.Integer, nullable=True),
    )
    # Migration des donnees existantes : tout no_answer_destination deja rempli
    # devient l'etape 0 de la nouvelle chaine, pour ne rien perdre (aucune ligne
    # trouvee en pratique au moment d'ecrire cette migration, mais fait par
    # principe -- loi "toujours pouvoir rediter").
    op.execute("""
        INSERT INTO ring_group_failover_steps (id, ring_group_id, step_order, destination_type, destination)
        SELECT gen_random_uuid(), id, 0, 'extension', no_answer_destination
        FROM ring_groups
        WHERE no_answer_destination IS NOT NULL AND no_answer_destination != ''
    """)


def downgrade() -> None:
    op.drop_table('ring_group_failover_steps')
