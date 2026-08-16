"""Poller du backup cloud infra SIPV (TASK-S059) -- verifie chaque minute si
une connexion cloud a atteint son heure planifiee (fuseau propre a la
connexion) et si un cycle est du."""
import asyncio
import logging

from app.workers.backup_runner import run_scheduled

log = logging.getLogger("backup_poller")

_POLL_INTERVAL = 60  # seconds


async def run_backup_poller():
    while True:
        try:
            await run_scheduled()
        except Exception:
            log.exception("Iteration du poller de backup echouee")
        await asyncio.sleep(_POLL_INTERVAL)
