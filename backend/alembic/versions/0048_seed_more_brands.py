"""Seed catalogue PhoneModel -- 20 marques additionnelles fournies par Philippe
(liste de reference generique, pas de config_template -- juste les entrees,
comme demande explicitement : "on ne fait pas les code juste la liste")

Idempotent : n'insere que les paires (brand, model) absentes -- ne touche pas
aux modeles Grandstream deja seedes (TASK-023.18/0039), meme si Philippe a
aussi liste des modeles Grandstream (doublons exacts ignores, nouveaux ajoutes).

Revision ID: 0048_seed_more_brands
Revises: 0047_template_explicit_selection
Create Date: 2026-08-03
"""
from typing import Union, Sequence
import uuid
import sqlalchemy as sa
from alembic import op

revision: str = '0048_seed_more_brands'
down_revision: Union[str, Sequence[str], None] = '0047_template_explicit_selection'
branch_labels = None
depends_on = None

# (brand, model, device_type) -- device_type classe UNIQUEMENT par mot-cle
# explicite dans le nom fourni (Intercom/Softphone/Gateway), "telephone" par
# defaut pour tout le reste (y compris DECT/Wireless -- ce sont des postes,
# pas une categorie a part) -- pas de classification basee sur une
# connaissance produit externe non verifiee (zero supposition).
MODELS = [
    ("Alcatel", "Temporis IP100", "telephone"), ("Alcatel", "Temporis IP150", "telephone"),
    ("Alcatel", "Temporis IP200", "telephone"), ("Alcatel", "Temporis IP300", "telephone"),
    ("Alcatel", "Temporis IP600", "telephone"), ("Alcatel", "Temporis IP700G", "telephone"),
    ("Alcatel", "Temporis IP800", "telephone"), ("Alcatel", "Temporis IP1850", "telephone"),
    ("Alcatel", "Temporis IP2015", "telephone"),

    ("AudioCodes", "310HD", "telephone"), ("AudioCodes", "320HD", "telephone"),
    ("AudioCodes", "405HD", "telephone"), ("AudioCodes", "420HD", "telephone"),
    ("AudioCodes", "430HD", "telephone"), ("AudioCodes", "440HD", "telephone"),

    ("Cisco", "3905", "telephone"), ("Cisco", "6901", "telephone"), ("Cisco", "6911", "telephone"),
    ("Cisco", "6921", "telephone"), ("Cisco", "6941", "telephone"), ("Cisco", "6945", "telephone"),
    ("Cisco", "6961", "telephone"), ("Cisco", "7811", "telephone"), ("Cisco", "7821", "telephone"),
    ("Cisco", "7841", "telephone"), ("Cisco", "7861", "telephone"), ("Cisco", "7905", "telephone"),
    ("Cisco", "7906", "telephone"), ("Cisco", "7911", "telephone"), ("Cisco", "7912", "telephone"),
    ("Cisco", "7931", "telephone"), ("Cisco", "7940", "telephone"), ("Cisco", "7941", "telephone"),
    ("Cisco", "7942", "telephone"), ("Cisco", "7945", "telephone"), ("Cisco", "7960", "telephone"),
    ("Cisco", "7961", "telephone"), ("Cisco", "7962", "telephone"), ("Cisco", "7965", "telephone"),
    ("Cisco", "7970", "telephone"), ("Cisco", "7971", "telephone"), ("Cisco", "7975", "telephone"),
    ("Cisco", "8811", "telephone"), ("Cisco", "8841", "telephone"), ("Cisco", "8851", "telephone"),
    ("Cisco", "8861", "telephone"),

    ("CyberData", "Intercom", "intercom"), ("CyberData", "Intercom with Keypad", "intercom"),

    ("CounterPath", "Bria (Softphone)", "softphone"),

    ("Fanvil", "X1/X1P/X1S/X1SP", "telephone"), ("Fanvil", "X2P/X2CP", "telephone"),
    ("Fanvil", "X3G/X3S/X3SP", "telephone"), ("Fanvil", "X3SG", "telephone"),
    ("Fanvil", "X3U", "telephone"), ("Fanvil", "X4/X4G", "telephone"), ("Fanvil", "X4SG", "telephone"),
    ("Fanvil", "X4U", "telephone"), ("Fanvil", "X5S", "telephone"), ("Fanvil", "X5U", "telephone"),
    ("Fanvil", "X6", "telephone"), ("Fanvil", "X6U", "telephone"), ("Fanvil", "X7", "telephone"),
    ("Fanvil", "X7A", "telephone"), ("Fanvil", "X7C", "telephone"), ("Fanvil", "X210/X210i", "telephone"),

    ("FlyingVoice", "FIP11WP", "telephone"),

    ("Grandstream", "GAC2500", "telephone"), ("Grandstream", "GRP2634", "telephone"),
    ("Grandstream", "GRP2624", "telephone"), ("Grandstream", "GRP2616", "telephone"),
    ("Grandstream", "GRP2615", "telephone"), ("Grandstream", "GRP2614", "telephone"),
    ("Grandstream", "GRP2613", "telephone"), ("Grandstream", "GRP2612", "telephone"),
    ("Grandstream", "GXP3275", "telephone"), ("Grandstream", "GXP3240", "telephone"),
    ("Grandstream", "GXP2200", "telephone"), ("Grandstream", "GXP2170", "telephone"),
    ("Grandstream", "GXP2160", "telephone"), ("Grandstream", "GXP2140", "telephone"),
    ("Grandstream", "GXP2135", "telephone"), ("Grandstream", "GXP2130", "telephone"),
    ("Grandstream", "GXP2124", "telephone"), ("Grandstream", "GXP2120", "telephone"),
    ("Grandstream", "GXP2110", "telephone"), ("Grandstream", "GXP2100", "telephone"),
    ("Grandstream", "GXP1780/GXP1782", "telephone"), ("Grandstream", "GXP1760", "telephone"),
    ("Grandstream", "GXP1630", "telephone"), ("Grandstream", "GXP1628", "telephone"),
    ("Grandstream", "GXP1620/GXP1625", "telephone"), ("Grandstream", "GXP1610/GXP1615", "telephone"),
    ("Grandstream", "GXP1200", "telephone"), ("Grandstream", "GXP1450", "telephone"),
    ("Grandstream", "GXP1400", "telephone"), ("Grandstream", "GXP1100", "telephone"),
    ("Grandstream", "GXP280", "telephone"), ("Grandstream", "Gateway GXW4216", "ata"),
    ("Grandstream", "Gateway GXW4224", "ata"), ("Grandstream", "Gateway GXW4232", "ata"),
    ("Grandstream", "Gateway GXW4248", "ata"),

    ("Hitachi", "WIP-5000 (Wireless)", "telephone"),

    ("LG-Ericsson", "LIP-8802", "telephone"), ("LG-Ericsson", "LIP-8815", "telephone"),
    ("LG-Ericsson", "LIP-8820", "telephone"), ("LG-Ericsson", "LIP-8830", "telephone"),
    ("LG-Ericsson", "LIP-8840", "telephone"),

    ("Mitel/Aastra", "51i", "telephone"), ("Mitel/Aastra", "53i", "telephone"),
    ("Mitel/Aastra", "55i", "telephone"), ("Mitel/Aastra", "57i", "telephone"),
    ("Mitel/Aastra", "480i", "telephone"), ("Mitel/Aastra", "6730i", "telephone"),
    ("Mitel/Aastra", "6731i", "telephone"), ("Mitel/Aastra", "6735i", "telephone"),
    ("Mitel/Aastra", "6737i", "telephone"), ("Mitel/Aastra", "6739i", "telephone"),
    ("Mitel/Aastra", "6751i", "telephone"), ("Mitel/Aastra", "6753i", "telephone"),
    ("Mitel/Aastra", "6755i", "telephone"), ("Mitel/Aastra", "6757i", "telephone"),
    ("Mitel/Aastra", "6863i", "telephone"), ("Mitel/Aastra", "6865i", "telephone"),
    ("Mitel/Aastra", "6867i", "telephone"), ("Mitel/Aastra", "6869i", "telephone"),
    ("Mitel/Aastra", "9112i", "telephone"), ("Mitel/Aastra", "9133i", "telephone"),
    ("Mitel/Aastra", "9143i", "telephone"), ("Mitel/Aastra", "9480i", "telephone"),

    ("Panasonic", "KX-HDV100", "telephone"), ("Panasonic", "KX-HDV130", "telephone"),
    ("Panasonic", "KX-HDV230", "telephone"), ("Panasonic", "KX-HDV330", "telephone"),
    ("Panasonic", "KX-HDV430", "telephone"), ("Panasonic", "KX-TGP500", "telephone"),
    ("Panasonic", "KX-TGP550/551", "telephone"), ("Panasonic", "KX-TGP600", "telephone"),
    ("Panasonic", "KX-UT113", "telephone"), ("Panasonic", "KX-UT123", "telephone"),
    ("Panasonic", "KX-UT133", "telephone"), ("Panasonic", "KX-UT136", "telephone"),
    ("Panasonic", "KX-UT248", "telephone"), ("Panasonic", "KX-UT670", "telephone"),
    ("Panasonic", "KX-UDS124 (Cell Station)", "telephone"), ("Panasonic", "KX-UDT111 (Handset)", "telephone"),
    ("Panasonic", "KX-UDT121 (Handset)", "telephone"), ("Panasonic", "KX-UDT131 (Handset)", "telephone"),

    ("Polycom", "IP300/330/331", "telephone"), ("Polycom", "IP400/430", "telephone"),
    ("Polycom", "IP450", "telephone"), ("Polycom", "IP500/550/560", "telephone"),
    ("Polycom", "IP600/650", "telephone"), ("Polycom", "SoundStation (4/6/7xxx)", "telephone"),
    ("Polycom", "VVX 300/310", "telephone"), ("Polycom", "VVX 400/410", "telephone"),
    ("Polycom", "VVX 500", "telephone"), ("Polycom", "VVX 600", "telephone"),
    ("Polycom", "VVX 1500", "telephone"), ("Polycom", "SpectraLink 8002 (Wireless)", "telephone"),
    ("Polycom", "SpectraLink 8440/8450/8452 (Wireless)", "telephone"),

    ("Linksys/Sipura", "SPA-301", "telephone"), ("Linksys/Sipura", "SPA-303", "telephone"),
    ("Linksys/Sipura", "SPA-501G", "telephone"), ("Linksys/Sipura", "SPA-502G", "telephone"),
    ("Linksys/Sipura", "SPA-504G", "telephone"), ("Linksys/Sipura", "SPA-508G", "telephone"),
    ("Linksys/Sipura", "SPA-509G", "telephone"), ("Linksys/Sipura", "SPA-525G2", "telephone"),
    ("Linksys/Sipura", "SPA-525G", "telephone"), ("Linksys/Sipura", "SPA-841", "telephone"),
    ("Linksys/Sipura", "SPA-901", "telephone"), ("Linksys/Sipura", "SPA-921/922", "telephone"),
    ("Linksys/Sipura", "SPA-941/942", "telephone"), ("Linksys/Sipura", "SPA-962", "telephone"),
    ("Linksys/Sipura", "SPA-1000/1001", "telephone"), ("Linksys/Sipura", "SPA-2000/2002", "telephone"),
    ("Linksys/Sipura", "PAP2", "telephone"),

    ("Snom", "300", "telephone"), ("Snom", "320", "telephone"), ("Snom", "360", "telephone"),
    ("Snom", "370", "telephone"), ("Snom", "D375", "telephone"), ("Snom", "710/D710", "telephone"),
    ("Snom", "715/D715", "telephone"), ("Snom", "720", "telephone"), ("Snom", "D725", "telephone"),
    ("Snom", "760", "telephone"), ("Snom", "D765", "telephone"), ("Snom", "820", "telephone"),
    ("Snom", "821", "telephone"), ("Snom", "870", "telephone"), ("Snom", "MeetingPoint", "telephone"),
    ("Snom", "M3 (Wireless)", "telephone"),

    ("Tiptel", "IP 28 XS", "telephone"), ("Tiptel", "IP 280", "telephone"),
    ("Tiptel", "IP 282", "telephone"), ("Tiptel", "IP 284", "telephone"),
    ("Tiptel", "IP 286", "telephone"), ("Tiptel", "IP 386", "telephone"),
    ("Tiptel", "VP 28", "telephone"),

    ("Uniden", "UIP200", "telephone"),

    ("Voice Operator Panel", "Voice Operator Panel (VOP)", "telephone"),

    ("VTech", "S1100", "telephone"), ("VTech", "S1210", "telephone"), ("VTech", "S1220", "telephone"),
    ("VTech", "S1410", "telephone"), ("VTech", "S1420", "telephone"), ("VTech", "S2100", "telephone"),
    ("VTech", "S2210/S2211", "telephone"), ("VTech", "S2220/S2221", "telephone"),
    ("VTech", "S2410", "telephone"), ("VTech", "S2420", "telephone"),
    ("VTech", "ErisTerminal VSP600", "telephone"), ("VTech", "ErisTerminal VSP715", "telephone"),
    ("VTech", "ErisTerminal VSP725", "telephone"), ("VTech", "ErisTerminal VSP735", "telephone"),
    ("VTech", "ErisStation VCS754", "telephone"),

    ("Yealink", "T19CM", "telephone"), ("Yealink", "T12", "telephone"), ("Yealink", "T18", "telephone"),
    ("Yealink", "T19", "telephone"), ("Yealink", "T20", "telephone"), ("Yealink", "T21", "telephone"),
    ("Yealink", "T22", "telephone"), ("Yealink", "T23", "telephone"), ("Yealink", "T26", "telephone"),
    ("Yealink", "T27", "telephone"), ("Yealink", "T28", "telephone"), ("Yealink", "T29", "telephone"),
    ("Yealink", "T30", "telephone"), ("Yealink", "T31", "telephone"), ("Yealink", "T32", "telephone"),
    ("Yealink", "T33", "telephone"), ("Yealink", "T38", "telephone"), ("Yealink", "T40", "telephone"),
    ("Yealink", "T41", "telephone"), ("Yealink", "T42", "telephone"), ("Yealink", "T43", "telephone"),
    ("Yealink", "T46", "telephone"), ("Yealink", "T48", "telephone"), ("Yealink", "T52", "telephone"),
    ("Yealink", "T53", "telephone"), ("Yealink", "T54", "telephone"), ("Yealink", "T56", "telephone"),
    ("Yealink", "T57", "telephone"), ("Yealink", "T58", "telephone"), ("Yealink", "CP860", "telephone"),
    ("Yealink", "CP920", "telephone"), ("Yealink", "CP960", "telephone"), ("Yealink", "VP59", "telephone"),
    ("Yealink", "VP530", "telephone"), ("Yealink", "W52 (DECT Wireless)", "telephone"),
    ("Yealink", "W53 (DECT Wireless)", "telephone"), ("Yealink", "W56 (DECT Wireless)", "telephone"),
    ("Yealink", "W60 (DECT Wireless)", "telephone"), ("Yealink", "W70 (DECT Wireless)", "telephone"),
    ("Yealink", "W80 (DECT Wireless)", "telephone"), ("Yealink", "W90 (DECT Wireless)", "telephone"),

    ("Other", "Custom", "telephone"),
]


def upgrade() -> None:
    conn = op.get_bind()
    existing = {
        (row[0], row[1])
        for row in conn.execute(sa.text("SELECT brand, model FROM phone_models")).fetchall()
    }
    for brand, model, dtype in MODELS:
        if (brand, model) in existing:
            continue
        conn.execute(
            sa.text(
                "INSERT INTO phone_models (id, brand, model, device_type, max_accounts, "
                "provisioning_protocol, is_active, created_at) "
                "VALUES (:id, :brand, :model, :dtype, 1, 'https', true, now())"
            ),
            {"id": str(uuid.uuid4()), "brand": brand, "model": model, "dtype": dtype},
        )


def downgrade() -> None:
    conn = op.get_bind()
    brands = sorted({b for b, _, _ in MODELS if b != "Grandstream"})
    conn.execute(sa.text("DELETE FROM phone_models WHERE brand = ANY(:brands)"), {"brands": brands})
