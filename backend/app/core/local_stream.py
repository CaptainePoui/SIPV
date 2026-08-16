"""
TASK-S033 : câblage réel de la musique d'attente (MOH) par tenant.

Approche additive volontaire, pour ne JAMAIS toucher au fichier statique
`local_stream.conf.xml` existant (5 flux par défaut déjà en place et
fonctionnels) : une seule modification ponctuelle de ce fichier (ajout d'un
<X-PRE-PROCESS include>, faite manuellement lors du déploiement, voir
TASKSIPV.md TASK-S033) pointe vers un répertoire `local_stream/` où CE module
écrit/réécrit un fichier <include> distinct par tenant -- jamais le fichier
principal. Même pattern déjà utilisé dans ce projet pour les gateways de
trunk (`sip_profiles/external/*.xml`).

hold_music (variable de canal) est réglé par tenant dans le directory XML
(_user_xml, xml_curl.py) pour pointer vers ce flux dédié.
"""
import asyncio
import logging
import shutil
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.config import settings
from app.models.tenant import Tenant
from app.models.moh import MohFile, TenantMohSelection

logger = logging.getLogger("local_stream")

LOCAL_STREAM_INCLUDE_DIR = Path(settings.FREESWITCH_DIR) / "conf/local_stream"
MOH_SOUNDS_BASE = Path(settings.FREESWITCH_DIR) / "sounds/sipv_moh"
MOH_UPLOAD_DIR = Path(settings.APP_DIR) / "backend/uploads/moh_files"


def moh_stream_name(account_number: str) -> str:
    # account_number est deja prefixe "t" (ex: "t1001") -- pas de "t" en plus ici.
    return f"moh_{account_number}"


async def regenerate_tenant_moh_stream(tenant_id, db: AsyncSession) -> None:
    """Recopie les fichiers sélectionnés de ce tenant dans son dossier dédié,
    réécrit SON fragment local_stream, recharge mod_local_stream. Best-effort
    total -- ne doit jamais faire planter l'appelant (upload/sélection MOH)
    si le serveur FreeSWITCH a un souci ; juste logué."""
    try:
        tenant = await db.get(Tenant, tenant_id)
        if not tenant:
            return
        stream_name = moh_stream_name(tenant.account_number)
        tenant_dir = MOH_SOUNDS_BASE / tenant.account_number
        include_file = LOCAL_STREAM_INCLUDE_DIR / f"{stream_name}.xml"

        result = await db.execute(
            select(MohFile).join(TenantMohSelection, TenantMohSelection.moh_file_id == MohFile.id)
            .where(TenantMohSelection.tenant_id == tenant_id, MohFile.is_active == True)
            .order_by(TenantMohSelection.sort_order)
        )
        files = result.scalars().all()

        if not files:
            # Rien de sélectionné -- retire le fragment s'il existait (le
            # tenant retombe implicitement sur le flux "default" du profil
            # SIP, comportement FreeSWITCH standard, rien à faire de plus).
            include_file.unlink(missing_ok=True)
            if tenant_dir.exists():
                shutil.rmtree(tenant_dir, ignore_errors=True)
            await _reload_local_stream()
            return

        if tenant_dir.exists():
            shutil.rmtree(tenant_dir, ignore_errors=True)
        tenant_dir.mkdir(parents=True, exist_ok=True)
        for i, f in enumerate(files):
            src = MOH_UPLOAD_DIR / f.filename
            if src.exists():
                shutil.copy2(src, tenant_dir / f"{i:03d}_{f.filename}")

        LOCAL_STREAM_INCLUDE_DIR.mkdir(parents=True, exist_ok=True)
        shuffle_value = "true" if tenant.moh_shuffle else "false"
        include_file.write_text(
            f"""<include>
  <directory name="{stream_name}" path="{tenant_dir}">
    <param name="rate" value="8000"/>
    <param name="shuffle" value="{shuffle_value}"/>
    <param name="channels" value="1"/>
    <param name="interval" value="20"/>
    <param name="timer-name" value="soft"/>
  </directory>
</include>
"""
        )
        await _reload_local_stream()
    except Exception:
        logger.exception("Régénération du flux MOH échouée pour tenant %s", tenant_id)


async def _reload_local_stream() -> None:
    """Recharge mod_local_stream via fs_cli (ligne de commande locale --
    aucun module ESL bgapi utilisé ici pour rester simple et synchrone)."""
    proc = await asyncio.create_subprocess_exec(
        "/usr/local/freeswitch/bin/fs_cli", "-x", "reload mod_local_stream",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        logger.warning("reload mod_local_stream a échoué: %s", err.decode(errors="replace")[:300])
