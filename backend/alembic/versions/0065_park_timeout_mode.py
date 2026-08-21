"""TASK-S061 : ParkingLot.timeout_return_mode -- choix explicite par lot entre
rappeler le poste qui a parque (dynamique, defaut) ou toujours renvoyer vers
return_extension (ex. Reception), peu importe qui a parque. Demande explicite
de Philippe (2026-08-20) : "je ne veux pas de poste de securite, je veux
avoir l'option de rappel [...] comme ca je peux selectionner la reception et
envoyer les park pas repondu la, ou de choisir l'option de base de rappeler
le poste qui a parke."

Revision ID: 0065_park_timeout_mode
Revises: 0064_parking_lot_active
Create Date: 2026-08-20
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0065_park_timeout_mode'
down_revision: Union[str, Sequence[str], None] = '0064_parking_lot_active'
branch_labels = None
depends_on = None

_ENUM_NAME = 'parking_timeout_return_mode_enum'


def upgrade() -> None:
    return_mode_enum = sa.Enum('parker', 'fixed', name=_ENUM_NAME)
    return_mode_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        'parking_lots',
        sa.Column('timeout_return_mode', return_mode_enum, nullable=False, server_default='parker'),
    )


def downgrade() -> None:
    op.drop_column('parking_lots', 'timeout_return_mode')
    sa.Enum(name=_ENUM_NAME).drop(op.get_bind(), checkfirst=True)
