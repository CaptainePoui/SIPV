"""
Detection centrale des collisions de numerotation interne par tenant
(TASK-S061, item 1 du plan Parcage -- backlog verrouille avant de construire
ParkingLot). Aucune nouvelle table : interroge directement les tables
existantes qui portent un numero composable dans le dialplan d'un tenant --
SIPExtension, RingGroup, PagingGroup, ParkingLot (pilote + plage de slots).

Hors scope, verifie dans le code avant d'ecrire ce module : IVR/Queue
(routes par destination_id, pas de numero direct), PickupGroup (code fixe
*8, purement organisationnel), Fax (rattache a un DID externe, namespace
different), messagerie vocale (codes etoiles fixes *97/*98). Confirme via
api/v1/endpoints/xml_curl.py (_dialplan_internal) que la resolution du
dialplan est deja filtree par tenant_id derive de l'appelant -- le controle
reste donc scope au tenant, jamais global (deux tenants peuvent reutiliser
les memes numeros sans risque).
"""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ivr import PagingGroup, ParkingLot, RingGroup
from app.models.sip import SIPExtension


@dataclass
class NumberConflict:
    object_type: str  # extension | ring_group | paging_group | parking_lot_pilot | parking_lot_range
    object_id: str
    number_or_range: str


@dataclass
class _Occupied:
    object_type: str
    object_id: str
    start: int
    end: int  # == start pour un numero unique
    raw: str


def _as_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start <= b_end and b_start <= a_end


async def _occupied_entries(
    db: AsyncSession, tenant_id, exclude_object: tuple[str, str] | None
) -> list[_Occupied]:
    def excluded(object_type: str, object_id) -> bool:
        return exclude_object is not None and exclude_object == (object_type, str(object_id))

    entries: list[_Occupied] = []

    result = await db.execute(select(SIPExtension).where(SIPExtension.tenant_id == tenant_id))
    for ext in result.scalars():
        if excluded("extension", ext.id):
            continue
        n = _as_int(ext.extension)
        if n is not None:
            entries.append(_Occupied("extension", str(ext.id), n, n, ext.extension))

    result = await db.execute(select(RingGroup).where(RingGroup.tenant_id == tenant_id))
    for rg in result.scalars():
        if excluded("ring_group", rg.id):
            continue
        n = _as_int(rg.extension)
        if n is not None:
            entries.append(_Occupied("ring_group", str(rg.id), n, n, rg.extension))

    result = await db.execute(select(PagingGroup).where(PagingGroup.tenant_id == tenant_id))
    for pg in result.scalars():
        if excluded("paging_group", pg.id):
            continue
        n = _as_int(pg.extension)
        if n is not None:
            entries.append(_Occupied("paging_group", str(pg.id), n, n, pg.extension))

    result = await db.execute(select(ParkingLot).where(ParkingLot.tenant_id == tenant_id))
    for lot in result.scalars():
        if excluded("parking_lot", lot.id):
            continue
        n = _as_int(lot.park_extension)
        if n is not None:
            entries.append(_Occupied("parking_lot_pilot", str(lot.id), n, n, lot.park_extension))
        # une plage occupe CHAQUE numero individuel qu'elle couvre, pas juste ses bornes
        entries.append(_Occupied(
            "parking_lot_range", str(lot.id),
            lot.parking_slots_start, lot.parking_slots_end,
            f"{lot.parking_slots_start}-{lot.parking_slots_end}",
        ))

    return entries


async def check_internal_number_available(
    db: AsyncSession,
    tenant_id,
    number: str,
    exclude_object: tuple[str, str] | None = None,
) -> list[NumberConflict]:
    """
    Conflits pour un numero unique (ex. une extension, le pilote d'un lot de
    parcage) dans le tenant donne. Liste vide = numero disponible.
    exclude_object = (object_type, object_id) de l'objet en cours d'edition,
    pour ignorer sa propre entree (ex. ("parking_lot", "<uuid>")).
    """
    n = _as_int(number)
    if n is None:
        return []
    entries = await _occupied_entries(db, tenant_id, exclude_object)
    return [
        NumberConflict(e.object_type, e.object_id, e.raw)
        for e in entries
        if _overlaps(n, n, e.start, e.end)
    ]


async def check_internal_range_available(
    db: AsyncSession,
    tenant_id,
    start: int,
    end: int,
    exclude_object: tuple[str, str] | None = None,
) -> list[NumberConflict]:
    """
    Conflits pour une plage (ex. les slots d'un lot de parcage) dans le
    tenant donne. Chaque numero de la plage est traite comme individuellement
    occupe -- deux plages qui se chevauchent, ou une plage qui recouvre une
    extension/ring group/paging group/pilote existant, sont en conflit.
    Liste vide = plage disponible.
    """
    entries = await _occupied_entries(db, tenant_id, exclude_object)
    return [
        NumberConflict(e.object_type, e.object_id, e.raw)
        for e in entries
        if _overlaps(start, end, e.start, e.end)
    ]
