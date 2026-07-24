"""TASK-023.9 -- ring group members (priorite/ordre/exclusion) + confirmation + horaire

Demande utilisateur : priorite du poste, ordre de sonnerie, confirmer avant de
repondre, poste temporairement exclu, horaire d'appartenance au groupe. La colonne
`members` (CSV) devient legacy -- les donnees existantes sont migrees vers la
nouvelle table ring_group_members (ordre de sonnerie = ordre dans le CSV).

Revision ID: 0032_ring_group_members_s023_9
Revises: 0031_forward_destination_types
Create Date: 2026-07-24
"""
from typing import Union, Sequence
import uuid
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = '0032_ring_group_members_s023_9'
down_revision: Union[str, Sequence[str], None] = '0031_forward_destination_types'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('ring_groups', sa.Column('confirm_before_answer', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('ring_groups', sa.Column('schedule_id', UUID(as_uuid=True), sa.ForeignKey('schedules.id', ondelete='SET NULL'), nullable=True))

    op.create_table(
        'ring_group_members',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('ring_group_id', UUID(as_uuid=True), sa.ForeignKey('ring_groups.id', ondelete='CASCADE'), nullable=False),
        sa.Column('extension_id', UUID(as_uuid=True), sa.ForeignKey('sip_extensions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('ring_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('temporarily_excluded', sa.Boolean(), nullable=False, server_default='false'),
    )

    # Migration de donnees : members (CSV de usernames) -> ring_group_members,
    # ordre de sonnerie = ordre dans le CSV. Postes non trouves (username orphelin)
    # ignores silencieusement plutot que de faire echouer toute la migration.
    conn = op.get_bind()
    groups = conn.execute(sa.text("SELECT id, tenant_id, members FROM ring_groups")).fetchall()
    for g in groups:
        usernames = [u.strip() for u in (g.members or "").split(",") if u.strip()]
        for order, username in enumerate(usernames):
            ext = conn.execute(
                sa.text("SELECT id FROM sip_extensions WHERE username = :u AND tenant_id = :t"),
                {"u": username, "t": g.tenant_id},
            ).fetchone()
            if not ext:
                continue
            conn.execute(
                sa.text(
                    "INSERT INTO ring_group_members (id, ring_group_id, extension_id, priority, ring_order, temporarily_excluded) "
                    "VALUES (:id, :rgid, :extid, 0, :order, false)"
                ),
                {"id": str(uuid.uuid4()), "rgid": g.id, "extid": ext.id, "order": order},
            )


def downgrade() -> None:
    op.drop_table('ring_group_members')
    op.drop_column('ring_groups', 'schedule_id')
    op.drop_column('ring_groups', 'confirm_before_answer')
