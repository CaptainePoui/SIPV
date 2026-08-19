"""TASK-032.2 (TASKERPCRM.md) : purge des CDR plus vieux que la retention
configuree par tenant (Tenant.cdr_retention_days, 1 an par defaut). Meme
convention que backup_poller.py -- poller asyncio in-process, pas de cron
systeme."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, delete

from app.core.database import AsyncSessionLocal
from app.models.tenant import Tenant
from app.models.cdr import CDR

log = logging.getLogger("cdr_retention")


async def purge_expired_cdr() -> dict:
    """Supprime, par tenant, les CDR dont start_time depasse la retention
    configuree. Retourne {tenant_id: rows_deleted} pour les tenants touches."""
    results = {}
    async with AsyncSessionLocal() as db:
        tenants = (await db.execute(select(Tenant))).scalars().all()
        for tenant in tenants:
            cutoff = datetime.now(timezone.utc) - timedelta(days=tenant.cdr_retention_days)
            result = await db.execute(
                delete(CDR).where(CDR.tenant_id == tenant.id, CDR.start_time < cutoff)
            )
            if result.rowcount:
                results[str(tenant.id)] = result.rowcount
                log.info("Purge CDR tenant %s : %d lignes (retention %dj)", tenant.account_number, result.rowcount, tenant.cdr_retention_days)
        await db.commit()
    return results
