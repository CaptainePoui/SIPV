"""Poller de purge CDR (TASK-032.2) -- meme pattern que backup_poller.py.
Toutes les heures suffit (requete DELETE idempotente, pas besoin de la minute
pres comme pour un envoi programme)."""
import asyncio
import logging

from app.workers.cdr_retention_runner import purge_expired_cdr

log = logging.getLogger("cdr_retention_poller")

_POLL_INTERVAL = 3600  # seconds


async def run_cdr_retention_poller():
    while True:
        try:
            await purge_expired_cdr()
        except Exception:
            log.exception("Iteration du poller de retention CDR echouee")
        await asyncio.sleep(_POLL_INTERVAL)
