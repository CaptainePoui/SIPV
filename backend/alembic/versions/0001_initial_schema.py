"""initial schema - tenants, sip_extensions, sip_trunks, tenant_dids + Asterisk Realtime tables

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-29

"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0001_initial'
down_revision: Union[str, Sequence[str], None] = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── SIPV Application Tables ────────────────────────────────────────────────

    op.create_table(
        'tenants',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('account_number', sa.String(50), nullable=False),
        sa.Column('company_name', sa.String(255), nullable=False),
        sa.Column('erpcrm_company_id', sa.String(36), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('context_prefix', sa.String(50), nullable=False),
        sa.Column('max_extensions', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('max_trunks', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('account_number'),
    )

    op.create_table(
        'sip_extensions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('extension', sa.String(20), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('username', sa.String(100), nullable=False),
        sa.Column('password', sa.String(255), nullable=False),
        sa.Column('voicemail_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('voicemail_email', sa.String(255), nullable=True),
        sa.Column('caller_id_name', sa.String(100), nullable=True),
        sa.Column('caller_id_number', sa.String(30), nullable=True),
        sa.Column('record_calls', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('max_contacts', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('asterisk_synced', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
    )

    op.create_table(
        'sip_trunks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('carrier_name', sa.String(100), nullable=False),
        sa.Column('host', sa.String(255), nullable=False),
        sa.Column('username', sa.String(100), nullable=True),
        sa.Column('password', sa.String(255), nullable=True),
        sa.Column('from_domain', sa.String(255), nullable=True),
        sa.Column('caller_id', sa.String(30), nullable=True),
        sa.Column('failover_trunk_id', sa.UUID(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('asterisk_synced', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['failover_trunk_id'], ['sip_trunks.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'tenant_dids',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('number', sa.String(20), nullable=False),
        sa.Column('label', sa.String(100), nullable=True),
        sa.Column('destination_type', sa.String(20), nullable=False, server_default='extension'),
        sa.Column('destination', sa.String(100), nullable=True),
        sa.Column('has_911', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('e911_address', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('number'),
    )

    # ── Asterisk PJSIP Realtime Tables ─────────────────────────────────────────
    # These mirror the Asterisk Realtime schema for PJSIP

    op.create_table(
        'ps_endpoints',
        sa.Column('id', sa.String(40), primary_key=True),
        sa.Column('transport', sa.String(40), nullable=True),
        sa.Column('aors', sa.String(200), nullable=True),
        sa.Column('auth', sa.String(40), nullable=True),
        sa.Column('context', sa.String(40), nullable=True),
        sa.Column('disallow', sa.String(200), nullable=True, server_default='all'),
        sa.Column('allow', sa.String(200), nullable=True, server_default='ulaw,alaw,g722'),
        sa.Column('direct_media', sa.String(3), nullable=True, server_default='no'),
        sa.Column('connected_line_method', sa.String(40), nullable=True),
        sa.Column('dtmf_mode', sa.String(20), nullable=True, server_default='rfc4733'),
        sa.Column('ice_support', sa.String(3), nullable=True, server_default='no'),
        sa.Column('force_rport', sa.String(3), nullable=True, server_default='yes'),
        sa.Column('rewrite_contact', sa.String(3), nullable=True, server_default='yes'),
        sa.Column('outbound_auth', sa.String(40), nullable=True),
        sa.Column('outbound_proxy', sa.String(256), nullable=True),
        sa.Column('callerid', sa.String(100), nullable=True),
        sa.Column('callerid_tag', sa.String(20), nullable=True),
        sa.Column('call_group', sa.String(40), nullable=True),
        sa.Column('pickup_group', sa.String(40), nullable=True),
        sa.Column('named_call_group', sa.String(40), nullable=True),
        sa.Column('named_pickup_group', sa.String(40), nullable=True),
        sa.Column('language', sa.String(10), nullable=True, server_default='fr'),
        sa.Column('tone_zone', sa.String(10), nullable=True),
        sa.Column('max_audio_streams', sa.Integer(), nullable=True),
        sa.Column('max_video_streams', sa.Integer(), nullable=True),
        sa.Column('mailboxes', sa.String(200), nullable=True),
        sa.Column('voicemail_extension', sa.String(40), nullable=True),
        sa.Column('mwi_subscribe_replaces_unsolicited', sa.String(3), nullable=True),
        sa.Column('accountcode', sa.String(40), nullable=True),
        sa.Column('rtp_symmetric', sa.String(3), nullable=True, server_default='yes'),
        sa.Column('send_rpid', sa.String(3), nullable=True),
        sa.Column('rpid_immediate', sa.String(3), nullable=True),
        sa.Column('timers_sess_expires', sa.Integer(), nullable=True),
        sa.Column('timers', sa.String(10), nullable=True),
        sa.Column('record_on_feature', sa.String(40), nullable=True),
        sa.Column('record_off_feature', sa.String(40), nullable=True),
        sa.Column('one_touch_recording', sa.String(3), nullable=True),
        sa.Column('trust_id_inbound', sa.String(3), nullable=True),
        sa.Column('trust_id_outbound', sa.String(3), nullable=True),
        sa.Column('use_ptime', sa.String(3), nullable=True),
        sa.Column('device_state_busy_at', sa.Integer(), nullable=True),
        sa.Column('t38_udptl', sa.String(3), nullable=True, server_default='no'),
        sa.Column('t38_udptl_ec', sa.String(20), nullable=True),
        sa.Column('t38_udptl_maxdatagram', sa.Integer(), nullable=True),
        sa.Column('fax_detect', sa.String(3), nullable=True, server_default='no'),
        sa.Column('fax_detect_timeout', sa.Integer(), nullable=True),
        sa.Column('srtp_tag_32', sa.String(3), nullable=True),
        sa.Column('media_encryption', sa.String(20), nullable=True, server_default='no'),
        sa.Column('media_encryption_optimistic', sa.String(3), nullable=True),
        sa.Column('use_avpf', sa.String(3), nullable=True),
        sa.Column('bundle', sa.String(3), nullable=True),
        sa.Column('webrtc', sa.String(3), nullable=True),
    )

    op.create_table(
        'ps_auths',
        sa.Column('id', sa.String(40), primary_key=True),
        sa.Column('auth_type', sa.String(20), nullable=True, server_default='userpass'),
        sa.Column('nonce_lifetime', sa.Integer(), nullable=True),
        sa.Column('md5_cred', sa.String(40), nullable=True),
        sa.Column('password', sa.String(80), nullable=True),
        sa.Column('realm', sa.String(40), nullable=True),
        sa.Column('username', sa.String(40), nullable=True),
    )

    op.create_table(
        'ps_aors',
        sa.Column('id', sa.String(40), primary_key=True),
        sa.Column('contact', sa.String(255), nullable=True),
        sa.Column('default_expiration', sa.Integer(), nullable=True, server_default='3600'),
        sa.Column('mailboxes', sa.String(80), nullable=True),
        sa.Column('max_contacts', sa.Integer(), nullable=True, server_default='3'),
        sa.Column('minimum_expiration', sa.Integer(), nullable=True, server_default='60'),
        sa.Column('remove_existing', sa.String(3), nullable=True, server_default='yes'),
        sa.Column('qualify_frequency', sa.Integer(), nullable=True, server_default='60'),
        sa.Column('authenticate_qualify', sa.String(3), nullable=True, server_default='no'),
        sa.Column('maximum_expiration', sa.Integer(), nullable=True, server_default='7200'),
        sa.Column('outbound_proxy', sa.String(256), nullable=True),
        sa.Column('support_path', sa.String(3), nullable=True),
    )

    op.create_table(
        'ps_contacts',
        sa.Column('id', sa.String(255), primary_key=True),
        sa.Column('uri', sa.String(255), nullable=True),
        sa.Column('expiration_time', sa.String(40), nullable=True),
        sa.Column('qualify_frequency', sa.Integer(), nullable=True),
        sa.Column('outbound_proxy', sa.String(256), nullable=True),
        sa.Column('path', sa.Text(), nullable=True),
        sa.Column('user_agent', sa.String(255), nullable=True),
        sa.Column('qualify_timeout', sa.Float(), nullable=True),
        sa.Column('reg_server', sa.String(20), nullable=True),
        sa.Column('authenticate_qualify', sa.String(3), nullable=True),
        sa.Column('via_addr', sa.String(40), nullable=True),
        sa.Column('via_port', sa.Integer(), nullable=True),
        sa.Column('call_id', sa.String(255), nullable=True),
        sa.Column('endpoint', sa.String(40), nullable=True),
        sa.Column('prune_on_boot', sa.String(3), nullable=True),
    )

    op.create_table(
        'extensions',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('context', sa.String(40), nullable=False),
        sa.Column('exten', sa.String(40), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('app', sa.String(40), nullable=True),
        sa.Column('appdata', sa.String(256), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('context', 'exten', 'priority'),
    )


def downgrade() -> None:
    op.drop_table('extensions')
    op.drop_table('ps_contacts')
    op.drop_table('ps_aors')
    op.drop_table('ps_auths')
    op.drop_table('ps_endpoints')
    op.drop_table('tenant_dids')
    op.drop_table('sip_trunks')
    op.drop_table('sip_extensions')
    op.drop_table('tenants')
