"""TASK-S008.2 -- voicemail : accueils audio, langue, transcription, heritage global/compagnie/poste

Revision ID: 0022_voicemail_s008_2
Revises: 0021_phone_physical
Create Date: 2026-07-23
"""
from typing import Union, Sequence
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = '0022_voicemail_s008_2'
down_revision: Union[str, Sequence[str], None] = '0021_phone_physical'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'telephony_settings',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('voicemail_delete_after_email', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('voicemail_max_messages', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('voicemail_max_message_length', sa.Integer(), nullable=False, server_default='300'),
        sa.Column('voicemail_language', sa.String(length=5), nullable=False, server_default='fr'),
    )
    # Une seule ligne (singleton) -- valeurs par defaut = comportement actuel avant
    # TASK-S008.2 (delete_after_email=False, max_messages=100, language=fr) sauf
    # max_message_length qui passe de 180s a 300s (5 min) par decision explicite.
    op.execute("INSERT INTO telephony_settings (id) VALUES (gen_random_uuid())")

    op.add_column('tenants', sa.Column('voicemail_delete_after_email', sa.Boolean(), nullable=True))

    op.add_column('voicemail_boxes', sa.Column('language', sa.String(length=5), nullable=False, server_default='fr'))
    op.add_column('voicemail_boxes', sa.Column('transcription_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('voicemail_boxes', sa.Column('temp_greeting_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('voicemail_boxes', sa.Column('greeting_unavailable_path', sa.String(length=255), nullable=True))
    op.add_column('voicemail_boxes', sa.Column('greeting_busy_path', sa.String(length=255), nullable=True))
    op.add_column('voicemail_boxes', sa.Column('greeting_name_path', sa.String(length=255), nullable=True))
    op.add_column('voicemail_boxes', sa.Column('greeting_temp_path', sa.String(length=255), nullable=True))

    # delete_after_email devient nullable (None = herite compagnie->global). Aucune
    # ligne existante actuellement (verifie avant migration) donc pas de backfill requis,
    # mais ALTER COLUMN reste necessaire pour les BD qui en auraient.
    op.alter_column('voicemail_boxes', 'delete_after_email', existing_type=sa.Boolean(), nullable=True, server_default=None)
    op.alter_column('voicemail_boxes', 'max_message_length', existing_type=sa.Integer(), server_default='300')


def downgrade() -> None:
    op.alter_column('voicemail_boxes', 'max_message_length', existing_type=sa.Integer(), server_default='180')
    op.execute("UPDATE voicemail_boxes SET delete_after_email = false WHERE delete_after_email IS NULL")
    op.alter_column('voicemail_boxes', 'delete_after_email', existing_type=sa.Boolean(), nullable=False, server_default='false')
    op.drop_column('voicemail_boxes', 'greeting_temp_path')
    op.drop_column('voicemail_boxes', 'greeting_name_path')
    op.drop_column('voicemail_boxes', 'greeting_busy_path')
    op.drop_column('voicemail_boxes', 'greeting_unavailable_path')
    op.drop_column('voicemail_boxes', 'temp_greeting_enabled')
    op.drop_column('voicemail_boxes', 'transcription_enabled')
    op.drop_column('voicemail_boxes', 'language')
    op.drop_column('tenants', 'voicemail_delete_after_email')
    op.drop_table('telephony_settings')
