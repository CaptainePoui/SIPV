"""
TASK-S047 (correction de conception decouverte 2026-08-07) : _dialplan_public()
(xml_curl.py) route reellement les appels entrants en lisant InboundRoute --
JAMAIS TenantDID, malgre le commentaire historique de sync.py qui affirmait le
contraire. Rien ne creait ni ne mettait a jour l'InboundRoute correspondante
quand un DID etait modifie depuis ERPCRM (TenantDID) ou depuis l'admin SIPV --
un changement de destination fait via l'UI habituelle n'avait donc aucun effet
sur un vrai appel entrant. Ce module centralise la synchronisation TenantDID ->
InboundRoute, appele depuis dids.py (chemin SIPV natif) et sync.py (chemin
ERPCRM maitre) pour ne pas dupliquer la logique aux deux endroits.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.sip import TenantDID
from app.models.dialplan import InboundRoute


async def sync_inbound_route_from_did(did: TenantDID, db: AsyncSession) -> None:
    """Cree, met a jour ou supprime l'InboundRoute miroir de ce TenantDID.
    N'appelle PAS commit() -- le caller commit deja le TenantDID dans la meme
    transaction, on veut les deux ecritures atomiques."""
    result = await db.execute(select(InboundRoute).where(InboundRoute.did_id == did.id))
    route = result.scalar_one_or_none()
    if route is None:
        result = await db.execute(select(InboundRoute).where(InboundRoute.did_number == did.number, InboundRoute.did_id.is_(None)))
        route = result.scalar_one_or_none()

    if not did.destination_type or not did.destination or not did.is_active:
        # Pas de destination configuree (ou DID desactive) -- aucune route reelle,
        # retirer l'InboundRoute existante s'il y en avait une (evite un routage
        # fantome vers une ancienne destination).
        if route is not None:
            await db.delete(route)
        return

    if route is None:
        route = InboundRoute(
            tenant_id=did.tenant_id, did_id=did.id, did_number=did.number,
            name=did.label or did.number,
            destination_type=did.destination_type, destination=did.destination,
            is_active=did.is_active,
            after_message_destination_type=did.after_message_destination_type,
            after_message_destination=did.after_message_destination,
        )
        db.add(route)
        return

    route.did_id = did.id
    route.did_number = did.number
    route.name = did.label or did.number
    route.destination_type = did.destination_type
    route.destination = did.destination
    route.is_active = did.is_active
    route.after_message_destination_type = did.after_message_destination_type
    route.after_message_destination = did.after_message_destination
    route.asterisk_synced = False
