"""TASK-S054 : SipvServer.sip_inbound_ip / sip_outbound_ip -- le fournisseur SIP
exige 2 IP publiques distinctes pour les canaux (entrant / sortant). Champs de
reference seulement, pas encore appliques a aucun binding reseau reel (l'IP n'est
pas encore connue par l'utilisateur au moment d'ecrire cette migration).

Revision ID: 0058_server_sip_channel_ips
Revises: 0057_ring_group_failover_steps
Create Date: 2026-08-07
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0058_server_sip_channel_ips'
down_revision: Union[str, Sequence[str], None] = '0057_ring_group_failover_steps'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sipv_servers', sa.Column('sip_inbound_ip', sa.String(45), nullable=True))
    op.add_column('sipv_servers', sa.Column('sip_outbound_ip', sa.String(45), nullable=True))


def downgrade() -> None:
    op.drop_column('sipv_servers', 'sip_outbound_ip')
    op.drop_column('sipv_servers', 'sip_inbound_ip')
