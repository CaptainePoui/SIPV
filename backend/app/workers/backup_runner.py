"""Runner du backup cloud infra SIPV (TASK-S059). Un seul dump physique par
execution, reutilise pour tous les cycles/clouds dus a ce moment -- pas de
triple pg_dump si plusieurs cycles coincident le meme jour.

Deux points d'entree :
- run_scheduled() : appele par le poller a intervalle court, evalue quels
  connexions/cycles sont dus MAINTENANT (heure + fuseau propres a chaque
  connexion cloud).
- run_manual() : bouton "Backup maintenant" -- ignore l'heure planifiee,
  pousse immediatement vers tous les cycles actifs de chaque cloud connecte.
"""
import logging
import subprocess
import tarfile
import tempfile
from datetime import datetime, date
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.config import settings
from app.core.crypto import decrypt
from app.core.database import AsyncSessionLocal
from app.models.backup import CloudBackupConnection, BackupCycle, BackupRunLog
from app.core import backup_cloud

log = logging.getLogger("backup_runner")

BACKEND_DIR = Path(__file__).resolve().parents[2]

# Capacite de reconstruction complete du serveur (meme demande que TASK-035
# ERPCRM, 2026-08-15) : serveur neuf + restauration de cette archive +
# ajustement des IPv4 doit suffire a remonter SIPV. Contient, en plus de la
# DB : secrets (.env), certs TLS s2s, unites systemd, config Kamailio/
# FreeSWITCH, MOH. PAS les enregistrements d'appel (recordings/) -- hors
# scope de ce backup infra, sujet distinct (TASK-S012.1/TASK-034 ERPCRM,
# stockage cloud CLIENT). Pas de chiffrement separe de l'archive (meme
# decision que cote ERPCRM) -- le serveur est deja le vecteur d'attaque
# principal et expose ces memes secrets en clair.
CONFIG_PATHS = [
    (BACKEND_DIR / ".env", "config/backend.env"),
    (BACKEND_DIR / "certs", "config/certs"),
    (Path("/etc/systemd/system/sipv-backend.service"), "config/systemd/sipv-backend.service"),
    (Path("/etc/systemd/system/sipv-backend-tls.service"), "config/systemd/sipv-backend-tls.service"),
    (Path("/etc/kamailio/kamailio.cfg"), "config/kamailio.cfg"),
    (Path("/etc/freeswitch/vars.xml"), "config/freeswitch/vars.xml"),
    (Path(settings.FREESWITCH_DIR) / "conf/local_stream", "config/freeswitch/local_stream"),
    (Path(settings.FREESWITCH_DIR) / "sounds/sipv_moh_backups", "moh"),
]


def _build_dump() -> Path:
    """pg_dump + config serveur (voir CONFIG_PATHS) dans une seule archive
    tar.gz temporaire."""
    parsed = urlparse(settings.DATABASE_URL)
    tmp_dir = Path(tempfile.mkdtemp(prefix="sipv_backup_"))
    sql_path = tmp_dir / "sipv_db.sql"

    env = {"PGPASSWORD": parsed.password or ""}
    subprocess.run(
        [
            "pg_dump", "-h", parsed.hostname or "localhost", "-p", str(parsed.port or 5432),
            "-U", parsed.username or "", "-d", (parsed.path or "/").lstrip("/"),
            "-f", str(sql_path),
        ],
        check=True, env=env,
    )

    archive_path = tmp_dir / "sipv_backup.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(sql_path, arcname="sipv_db.sql")
        for src, arcname in CONFIG_PATHS:
            try:
                if src.exists():
                    tar.add(src, arcname=arcname)
                else:
                    log.warning("Backup: fichier de config manquant, ignore: %s", src)
            except PermissionError:
                log.warning("Backup: acces refuse, ignore: %s", src)
    sql_path.unlink()
    return archive_path


def _remote_filename(frequency_type: str, when: date) -> str:
    return f"sipv_{frequency_type}_{when.isoformat()}.tar.gz"


def _is_cycle_due(cycle: BackupCycle, today: date) -> bool:
    if cycle.frequency_type == "daily":
        return True
    if cycle.frequency_type == "weekly":
        return today.weekday() == cycle.day_of_week
    if cycle.frequency_type == "monthly":
        return today.day == cycle.day_of_month
    if cycle.frequency_type == "yearly":
        return today.day == cycle.day_of_month and today.month == cycle.month_of_year
    return False


async def _rotate_and_upload(db, connection: CloudBackupConnection, cycle: BackupCycle, archive_path: Path, manual: bool):
    refresh_token = decrypt(connection.refresh_token_enc)
    client_id, client_secret = backup_cloud.resolve_credentials(connection)
    filename = _remote_filename(cycle.frequency_type, date.today())
    prefix = f"sipv_{cycle.frequency_type}_"

    log_row = BackupRunLog(cycle_id=cycle.id, provider=connection.provider, filename=filename, success=False, triggered_manually=manual)
    try:
        if connection.provider == "dropbox":
            await backup_cloud.dropbox_upload(client_id, client_secret, refresh_token, archive_path, filename, connection.bandwidth_limit_kbps)
            if cycle.retention_enabled:
                existing = await backup_cloud.dropbox_list_backups(client_id, client_secret, refresh_token)
                matching = sorted([e for e in existing if e["name"].startswith(prefix)], key=lambda e: e["name"])
                for old in matching[:-cycle.retention_count] if len(matching) > cycle.retention_count else []:
                    await backup_cloud.dropbox_delete(client_id, client_secret, refresh_token, old["path_lower"])
        else:
            backup_cloud.google_drive_upload(client_id, client_secret, refresh_token, archive_path, filename, connection.bandwidth_limit_kbps)
            if cycle.retention_enabled:
                existing = backup_cloud.google_drive_list_backups(client_id, client_secret, refresh_token)
                matching = sorted([e for e in existing if e["name"].startswith(prefix)], key=lambda e: e["name"])
                for old in matching[:-cycle.retention_count] if len(matching) > cycle.retention_count else []:
                    backup_cloud.google_drive_delete(client_id, client_secret, refresh_token, old["id"])
        log_row.success = True
    except Exception as e:
        log.exception("Echec backup %s / cycle %s", connection.provider, cycle.frequency_type)
        log_row.error_message = str(e)[:2000]
    log_row.finished_at = datetime.now()
    db.add(log_row)
    await db.commit()
    return log_row.success


async def run_manual() -> list[dict]:
    results = []
    async with AsyncSessionLocal() as db:
        connections = (await db.execute(select(CloudBackupConnection).where(CloudBackupConnection.enabled == True))).scalars().all()
        connections = [c for c in connections if c.refresh_token_enc]
        cycles = (await db.execute(select(BackupCycle).where(BackupCycle.enabled == True))).scalars().all()
        if not connections or not cycles:
            return results

        archive_path = _build_dump()
        try:
            for connection in connections:
                for cycle in cycles:
                    success = await _rotate_and_upload(db, connection, cycle, archive_path, manual=True)
                    results.append({"provider": connection.provider, "cycle": cycle.frequency_type, "success": success})
        finally:
            archive_path.unlink(missing_ok=True)
            archive_path.parent.rmdir()
    return results


async def run_scheduled():
    async with AsyncSessionLocal() as db:
        connections = (await db.execute(select(CloudBackupConnection).where(CloudBackupConnection.enabled == True))).scalars().all()
        connections = [c for c in connections if c.refresh_token_enc]
        cycles = (await db.execute(select(BackupCycle).where(BackupCycle.enabled == True))).scalars().all()
        if not connections or not cycles:
            return

        archive_path: Path | None = None
        try:
            for connection in connections:
                now_local = datetime.now(ZoneInfo(connection.timezone))
                hh, mm = (int(x) for x in connection.backup_hour.split(":"))
                scheduled_today = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
                if now_local < scheduled_today:
                    continue  # heure pas encore atteinte aujourd'hui

                # Peu importe succes ou echec -- UNE tentative par jour par
                # connexion (meme fix que cote ERPCRM, evite une boucle de
                # reessai infinie sur une erreur permanente).
                already_attempted = await db.execute(
                    select(BackupRunLog).where(
                        BackupRunLog.provider == connection.provider,
                        BackupRunLog.started_at >= scheduled_today.astimezone(ZoneInfo("UTC")).replace(tzinfo=None),
                    )
                )
                if already_attempted.scalars().first():
                    continue

                due_cycles = [c for c in cycles if _is_cycle_due(c, now_local.date())]
                if not due_cycles:
                    continue
                if archive_path is None:
                    archive_path = _build_dump()
                for cycle in due_cycles:
                    await _rotate_and_upload(db, connection, cycle, archive_path, manual=False)
        finally:
            if archive_path is not None:
                archive_path.unlink(missing_ok=True)
                archive_path.parent.rmdir()
