"""Table sipv_servers + tenants.server_id -- fondation multi-serveur (TASK-S042)

Revision ID: 0044_sipv_servers
Revises: 0043_phone_provisioning_protocol
Create Date: 2026-08-02
"""
from typing import Union, Sequence
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = '0044_sipv_servers'
down_revision: Union[str, Sequence[str], None] = '0043_phone_provisioning_protocol'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'sipv_servers',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('hostname', sa.String(255), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column('tenants', sa.Column('server_id', UUID(as_uuid=True), sa.ForeignKey('sipv_servers.id', ondelete='SET NULL'), nullable=True))

    # Seed le serveur actuel + backfill tous les tenants existants dessus
    import uuid
    server_id = str(uuid.uuid4())
    conn = op.get_bind()
    conn.execute(sa.text(
        "INSERT INTO sipv_servers (id, name, hostname, ip_address, is_active, created_at) "
        "VALUES (:id, 'sipv-lab', 'sipv-lab', '192.168.1.55', true, now())"
    ), {"id": server_id})
    conn.execute(sa.text("UPDATE tenants SET server_id = :id WHERE server_id IS NULL"), {"id": server_id})


def downgrade() -> None:
    op.drop_column('tenants', 'server_id')
    op.drop_table('sipv_servers')
