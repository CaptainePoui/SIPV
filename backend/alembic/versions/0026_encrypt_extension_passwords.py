"""TASK-S039 -- chiffrer (Fernet) les mots de passe SIPExtension existants

Demande utilisateur : afficher le mot de passe SIP sur la fiche contact ERPCRM pour
configuration manuelle d'un telephone (provisioning automatique bloque sur certains
reseaux). Condition posee par l'utilisateur pour l'exposer : le chiffrer au repos.
Auparavant en clair (necessaire pour l'auth digest FreeSWITCH, mod_xml_curl dechiffre
maintenant a la volee dans xml_curl.py). Meme pattern Fernet que
provisioning.encrypted_admin_password.

Revision ID: 0026_encrypt_extension_passwords
Revises: 0025_extension_911_s010_2
Create Date: 2026-07-24
"""
from typing import Union, Sequence
import sqlalchemy as sa
from alembic import op

revision: str = '0026_encrypt_extension_passwords'
down_revision: Union[str, Sequence[str], None] = '0025_extension_911_s010_2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.core.crypto import encrypt

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, password FROM sip_extensions")).fetchall()
    for row in rows:
        conn.execute(
            sa.text("UPDATE sip_extensions SET password = :p WHERE id = :id"),
            {"p": encrypt(row.password), "id": row.id},
        )


def downgrade() -> None:
    from app.core.crypto import decrypt

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, password FROM sip_extensions")).fetchall()
    for row in rows:
        conn.execute(
            sa.text("UPDATE sip_extensions SET password = :p WHERE id = :id"),
            {"p": decrypt(row.password), "id": row.id},
        )
