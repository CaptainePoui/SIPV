"""TASK-S061 : ParkingLot.is_active -- desactiver un lot sans le supprimer
(coherent avec le reste du projet, jamais de create-only, voir memoire
feedback_always_editable). Demande de Philippe (2026-08-19) : "actif ou pas"
manquait dans les options exposees en ERPCRM.

Revision ID: 0064_parking_lot_active
Revises: 0063_parking_lot_announce
Create Date: 2026-08-19
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0064_parking_lot_active'
down_revision: Union[str, Sequence[str], None] = '0063_parking_lot_announce'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('parking_lots', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    op.drop_column('parking_lots', 'is_active')
