"""Zone de parcage par defaut (TASK-051, demande Philippe 2026-10-11) : chaque tenant vient avec la sienne, creee
avec le tenant ; une migration de tenant n'offre plus de choix pour le parcage (la destination a toujours sa propre
zone, creee si elle n'en a pas ; la source garde la sienne). Les telephones provisionnes s'y attendent (touche Park 700,
park surveilles 701-703)."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ivr import ParkingLot

DEFAULT_NAME = "Parcage"
DEFAULT_PILOT = "700"
DEFAULT_START, DEFAULT_END = 701, 720


def default_numbers() -> set[str]:
    return {DEFAULT_PILOT} | {str(n) for n in range(DEFAULT_START, DEFAULT_END + 1)}


async def has_parking(db: AsyncSession, tenant_id) -> bool:
    return (await db.execute(select(ParkingLot.id).where(ParkingLot.tenant_id == tenant_id).limit(1))).first() is not None


async def ensure_default_parking(db: AsyncSession, tenant_id) -> ParkingLot | None:
    """Cree la zone par defaut si le tenant n'en a aucune. Retourne la zone creee, sinon None. Ne commit pas."""
    if await has_parking(db, tenant_id):
        return None
    lot = ParkingLot(tenant_id=tenant_id, name=DEFAULT_NAME, park_extension=DEFAULT_PILOT,
                     parking_slots_start=DEFAULT_START, parking_slots_end=DEFAULT_END)
    db.add(lot)
    return lot
