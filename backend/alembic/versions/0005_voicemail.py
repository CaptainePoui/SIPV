"""add voicemail_boxes and voicemail_messages tables

Revision ID: 0005_voicemail
Revises: 0004_ivr
Create Date: 2026-06-29

"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0005_voicemail'
down_revision: Union[str, Sequence[str], None] = '0004_ivr'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'voicemail_boxes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('extension_id', sa.UUID(), nullable=True),
        sa.Column('mailbox', sa.String(20), nullable=False),
        sa.Column('context', sa.String(40), nullable=False, server_default='default'),
        sa.Column('password', sa.String(20), nullable=False, server_default='1234'),
        sa.Column('fullname', sa.String(100), nullable=False),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('pager', sa.String(100), nullable=True),
        sa.Column('email_on_new', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('attach_message', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('delete_after_email', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('say_cid', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('say_duration', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('max_messages', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('max_message_length', sa.Integer(), nullable=False, server_default='180'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['extension_id'], ['sip_extensions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'voicemail_messages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('mailbox_id', sa.UUID(), nullable=False),
        sa.Column('msgnum', sa.Integer(), nullable=False),
        sa.Column('folder', sa.String(20), nullable=False, server_default='INBOX'),
        sa.Column('callerid', sa.String(100), nullable=True),
        sa.Column('origtime', sa.String(20), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('recording_path', sa.String(255), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('email_sent', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['mailbox_id'], ['voicemail_boxes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # Asterisk voicemail Realtime table (for direct Asterisk integration)
    op.create_table(
        'voicemessages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('msgnum', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('dir', sa.String(255), nullable=True),
        sa.Column('context', sa.String(80), nullable=True),
        sa.Column('macrocontext', sa.String(80), nullable=True),
        sa.Column('callerid', sa.String(40), nullable=True),
        sa.Column('origtime', sa.String(40), nullable=True),
        sa.Column('duration', sa.String(20), nullable=True),
        sa.Column('mailboxuser', sa.String(80), nullable=True),
        sa.Column('mailboxcontext', sa.String(80), nullable=True),
        sa.Column('flag', sa.String(30), nullable=True),
        sa.Column('msg_id', sa.String(40), nullable=True),
        sa.Column('recording', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('voicemessages')
    op.drop_table('voicemail_messages')
    op.drop_table('voicemail_boxes')
