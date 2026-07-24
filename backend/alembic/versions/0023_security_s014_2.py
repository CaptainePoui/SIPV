"""TASK-S014.2 -- security: ACL par poste, seuil tentatives echouees

Revision ID: 0023_security_s014_2
Revises: 0022_voicemail_s008_2
Create Date: 2026-07-23
"""
from typing import Union, Sequence
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = '0023_security_s014_2'
down_revision: Union[str, Sequence[str], None] = '0022_voicemail_s008_2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('acl_rules', sa.Column('extension_id', UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'acl_rules_extension_id_fkey', 'acl_rules', 'sip_extensions',
        ['extension_id'], ['id'], ondelete='CASCADE',
    )
    op.add_column('fraud_rules', sa.Column('max_failed_auth_attempts', sa.Integer(), nullable=True, server_default='5'))


def downgrade() -> None:
    op.drop_column('fraud_rules', 'max_failed_auth_attempts')
    op.drop_constraint('acl_rules_extension_id_fkey', 'acl_rules', type_='foreignkey')
    op.drop_column('acl_rules', 'extension_id')
