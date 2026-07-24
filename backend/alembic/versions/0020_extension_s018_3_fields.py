"""TASK-S018.3 -- sip_extensions: identification, plan d'appel, renvois, DND, codec_list

Revision ID: 0020_extension_s018_3
Revises: 0019_extension_transport
Create Date: 2026-07-23
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0020_extension_s018_3'
down_revision: Union[str, Sequence[str], None] = '0019_extension_transport'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sip_extensions', sa.Column('codec_list', sa.String(length=60), nullable=False, server_default='ulaw,alaw,g722,g729'))
    # Backfill : si un codec unique etait deja choisi, le mettre en tete de la liste
    # (respecte le choix existant plutot que de l'ecraser silencieusement).
    op.execute("""
        UPDATE sip_extensions SET codec_list =
            CASE codec
                WHEN 'ulaw' THEN 'ulaw,alaw,g722,g729'
                WHEN 'alaw' THEN 'alaw,ulaw,g722,g729'
                WHEN 'g722' THEN 'g722,ulaw,alaw,g729'
                WHEN 'g729' THEN 'g729,ulaw,alaw,g722'
                ELSE 'ulaw,alaw,g722,g729'
            END
        WHERE codec IS NOT NULL
    """)
    op.drop_column('sip_extensions', 'codec')

    op.add_column('sip_extensions', sa.Column('site', sa.String(length=100), nullable=True))
    op.add_column('sip_extensions', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('sip_extensions', sa.Column('call_permission', sa.String(length=20), nullable=False, server_default='international'))
    op.add_column('sip_extensions', sa.Column('forward_immediate_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('sip_extensions', sa.Column('forward_immediate_destination', sa.String(length=100), nullable=True))
    op.add_column('sip_extensions', sa.Column('forward_busy_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('sip_extensions', sa.Column('forward_busy_destination', sa.String(length=100), nullable=True))
    op.add_column('sip_extensions', sa.Column('forward_no_answer_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('sip_extensions', sa.Column('forward_no_answer_destination', sa.String(length=100), nullable=True))
    op.add_column('sip_extensions', sa.Column('forward_no_answer_delay_seconds', sa.Integer(), nullable=True, server_default='20'))
    op.add_column('sip_extensions', sa.Column('forward_offline_destination', sa.String(length=100), nullable=True))
    op.add_column('sip_extensions', sa.Column('dnd_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('sip_extensions', sa.Column('dnd_locked', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('sip_extensions', sa.Column('auto_answer_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('sip_extensions', sa.Column('max_concurrent_calls', sa.Integer(), nullable=True))
    op.add_column('sip_extensions', sa.Column('distinctive_ring', sa.String(length=50), nullable=True))
    op.add_column('sip_extensions', sa.Column('record_mode', sa.String(length=10), nullable=False, server_default='manual'))


def downgrade() -> None:
    op.drop_column('sip_extensions', 'record_mode')
    op.drop_column('sip_extensions', 'distinctive_ring')
    op.drop_column('sip_extensions', 'max_concurrent_calls')
    op.drop_column('sip_extensions', 'auto_answer_enabled')
    op.drop_column('sip_extensions', 'dnd_locked')
    op.drop_column('sip_extensions', 'dnd_enabled')
    op.drop_column('sip_extensions', 'forward_offline_destination')
    op.drop_column('sip_extensions', 'forward_no_answer_delay_seconds')
    op.drop_column('sip_extensions', 'forward_no_answer_destination')
    op.drop_column('sip_extensions', 'forward_no_answer_enabled')
    op.drop_column('sip_extensions', 'forward_busy_destination')
    op.drop_column('sip_extensions', 'forward_busy_enabled')
    op.drop_column('sip_extensions', 'forward_immediate_destination')
    op.drop_column('sip_extensions', 'forward_immediate_enabled')
    op.drop_column('sip_extensions', 'call_permission')
    op.drop_column('sip_extensions', 'description')
    op.drop_column('sip_extensions', 'site')

    op.add_column('sip_extensions', sa.Column('codec', sa.String(length=10), nullable=True))
    op.execute("""
        UPDATE sip_extensions SET codec = split_part(codec_list, ',', 1)
        WHERE codec_list IS NOT NULL AND codec_list != ''
    """)
    op.drop_column('sip_extensions', 'codec_list')
