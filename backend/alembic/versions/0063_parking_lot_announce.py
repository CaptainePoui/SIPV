"""TASK-S061 : ParkingLot.announce_slot -- controle de l'annonce vocale du
slot choisi en mode auto (valet_announce_slot). False par defaut, active
explicitement desactive par Philippe pour son usage actuel (blind transfer
uniquement, 2026-08-19).

Revision ID: 0063_parking_lot_announce
Revises: 0062_cdr_retention
Create Date: 2026-08-19
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0063_parking_lot_announce'
down_revision: Union[str, Sequence[str], None] = '0062_cdr_retention'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('parking_lots', sa.Column('announce_slot', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('parking_lots', 'announce_slot')
