"""TASK-023.18 -- seed catalogue PhoneModel Grandstream (65 modeles)

Modeles extraits des fichiers de reference P-code fournis par l'utilisateur
(/home/simpleip/GrandStream/Template_Config_Pcode/config-template/*.txt) --
un modele par famille de fichier (garde la version firmware la plus recente par
famille), device_type classe par prefixe de nom (telephone/ata/intercom/softphone).
Idempotent : ne fait rien si des modeles Grandstream existent deja (guard sur brand).

Revision ID: 0039_seed_grandstream
Revises: 0038_phone_buttons
Create Date: 2026-07-24
"""
from typing import Union, Sequence
import uuid
import sqlalchemy as sa
from alembic import op

revision: str = '0039_seed_grandstream'
down_revision: Union[str, Sequence[str], None] = '0038_phone_buttons'
branch_labels = None
depends_on = None

MODELS = [
    ("DP715", "1.0.0.33", "telephone"), ("DP755", "1.0.3.27", "telephone"), ("DP75X", "1.0.21.33", "telephone"),
    ("GAC2500", "1.0.3.51", "telephone"), ("GAC2570", "1.0.3.33", "telephone"),
    ("GDS3702", "1.0.3.18", "intercom"), ("GDS3705", "1.0.3.18", "intercom"), ("GDS370X", "1.0.3.11", "intercom"),
    ("GDS3710", "1.0.13.15", "intercom"), ("GDS3712", "1.0.13.15", "intercom"), ("GDS372X", "1.0.3.9", "intercom"),
    ("GHP63X", "1.0.1.50", "telephone"), ("GHP6XX", "1.0.1.97", "telephone"),
    ("GRP260X", "1.0.7.64", "telephone"), ("GRP261X/2X/3X/5X/7X", "1.0.13.127", "telephone"),
    ("GS_WAVE", "1.0", "softphone"),
    ("GSC3505", "1.0.3.16", "intercom"), ("GSC3506", "1.0.5.22", "intercom"), ("GSC3510", "1.0.3.16", "intercom"),
    ("GSC3516", "1.0.5.22", "intercom"), ("GSC3518HS", "1.0.1.15", "intercom"), ("GSC3570", "1.0.7.10", "intercom"),
    ("GSC3574-GSC3575", "1.0.3.6", "intercom"),
    ("GVC320X", "1.0.3.69", "telephone"), ("GVC3210", "1.0.1.76", "telephone"), ("GVC3212", "1.0.1.6", "telephone"),
    ("GVC3220", "1.0.1.37", "telephone"),
    ("GXP110X", "1.0.8.6", "telephone"), ("GXP116X", "1.0.8.9", "telephone"), ("GXP140X", "1.0.8.9", "telephone"),
    ("GXP1450", "1.0.8.9", "telephone"), ("GXP16XX", "1.0.7.81", "telephone"), ("GXP17XX", "1.0.1.133", "telephone"),
    ("GXP2124", "1.0.8.6", "telephone"), ("GXP2130/40/60/70/35", "1.0.11.106", "telephone"),
    ("GXP21XX", "1.0.8.6", "telephone"), ("GXP2200", "1.0.3.27", "telephone"),
    ("GXV300X", "1.2.3.7", "telephone"), ("GXV3140", "1.0.7.80", "telephone"), ("GXV3175", "1.0.3.76", "telephone"),
    ("GXV3175V2", "1.0.1.55", "telephone"), ("GXV3240", "1.0.3.227", "telephone"), ("GXV3275", "1.0.3.227", "telephone"),
    ("GXV33XX", "1.0", "intercom"), ("GXV34X0", "1.0.5.32", "telephone"), ("GXV3500", "1.0.3.17", "intercom"),
    ("GXW410X", "1.4.1.5", "ata"), ("GXW42XX_V1", "1.0.23.15", "ata"), ("GXW42XX_V2", "1.0.33.11", "ata"),
    ("HT502", "1.0.16.2", "ata"), ("HT503", "1.0.16.3", "ata"), ("HT701/HT702", "1.0.10.3", "ata"),
    ("HT704", "1.0.10.3", "ata"), ("HT80X", "1.0.65.1", "ata"), ("HT80X_V2", "1.0.15.1", "ata"),
    ("HT813", "1.0.19.6", "ata"), ("HT818", "1.0.65.1", "ata"), ("HT81X", "1.0.65.1", "ata"),
    ("HT81X_V2", "1.0.15.1", "ata"), ("HT8X1", "1.0.9.9", "ata"), ("HTX86", "1.1.0.45", "ata"),
    ("WP810/822/825", "1.0.11.81", "telephone"), ("WP820", "1.0.7.85", "telephone"),
    ("WP856", "1.0.3.16", "telephone"), ("WP8X6", "1.0.3.35", "telephone"),
]


def upgrade() -> None:
    conn = op.get_bind()
    existing = conn.execute(sa.text("SELECT count(*) FROM phone_models WHERE brand = 'Grandstream'")).scalar()
    if existing:
        return
    for model, fw, dtype in MODELS:
        conn.execute(
            sa.text(
                "INSERT INTO phone_models (id, brand, model, firmware_version, device_type, "
                "max_accounts, provisioning_protocol, is_active, created_at) "
                "VALUES (:id, 'Grandstream', :model, :fw, :dtype, 1, 'https', true, now())"
            ),
            {"id": str(uuid.uuid4()), "model": model, "fw": fw, "dtype": dtype},
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM phone_models WHERE brand = 'Grandstream'"))
