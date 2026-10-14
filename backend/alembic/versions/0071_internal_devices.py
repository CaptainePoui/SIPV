"""Appareils internes (TASK-027.3, 2026-10-11, Philippe : « on choisit le tenant d'abord, ca nous amene a une liste de
postes deja configures dans le tenant et on a juste a cocher les postes a l'interne ; on peut meme ajouter plusieurs
tenants ») : depuis 0069 tous les telephones ont l'adresse publique comme proxy SIP ; au bureau (meme reseau que le
serveur) la boucle NAT du routeur ne tient pas. Un poste coche « Interne » recoit l'adresse interne de son serveur.

- sip_extensions.internal_network (faux par defaut : rien ne change pour les postes existants)
- internal_network_tenants (serveur, tenant) : tenants affiches dans l'onglet

Revision ID: 0071_internal_devices
Revises: 0070_vpk_all_keys
Create Date: 2026-10-14
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = '0071_internal_devices'
down_revision: Union[str, Sequence[str], None] = '0070_vpk_all_keys'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sip_extensions", sa.Column("internal_network", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        "internal_network_tenants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("server_id", UUID(as_uuid=True), sa.ForeignKey("sipv_servers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("server_id", "tenant_id", name="uq_internal_network_tenant"),
    )


def downgrade() -> None:
    op.drop_table("internal_network_tenants")
    op.drop_column("sip_extensions", "internal_network")
