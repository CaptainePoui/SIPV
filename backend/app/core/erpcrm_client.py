"""
Client HTTP SIPV -> ERPCRM.
Utilise pour chercher/creer/lier un contact ERPCRM depuis une extension SIPV (TASK-S022).
Authentification par X-Api-Key (settings.SIPV_API_KEY) — jamais de compte utilisateur.
"""
import logging
import httpx
from app.core.config import settings

logger = logging.getLogger("erpcrm_client")

# CA privee ERPCRM<->SIPV (TASK-039 TLS inter-serveurs) -- verifie le certificat du
# port TLS dedie d'ERPCRM (8011), distinct du port HTTP existant (8010, inchange,
# reste utilise par le frontend).
_CA_PATH = "/home/sipv/sipv/backend/certs/ca.pem"


def _headers() -> dict:
    return {"X-Api-Key": settings.SIPV_API_KEY}


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=5.0, verify=_CA_PATH)


async def search_contact(name: str) -> dict | None:
    """Cherche un contact ERPCRM par nom. Retourne le premier resultat ou None."""
    async with _client() as client:
        resp = await client.get(
            f"{settings.ERPCRM_API_URL}/api/v1/contacts",
            params={"search": name},
            headers=_headers(),
        )
        resp.raise_for_status()
        results = resp.json()
        return results[0] if results else None


async def create_contact(first_name: str, last_name: str, extension: str) -> dict:
    """Cree un contact ERPCRM avec sipv_sync=true. Retourne le contact cree."""
    async with _client() as client:
        resp = await client.post(
            f"{settings.ERPCRM_API_URL}/api/v1/contacts",
            json={
                "first_name": first_name,
                "last_name": last_name,
                "extension": extension,
                "sipv_sync": True,
            },
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()


async def update_contact(contact_id: str, **fields) -> dict:
    """Met a jour un contact ERPCRM (sipv_sync, extension, etc.)."""
    async with _client() as client:
        resp = await client.put(
            f"{settings.ERPCRM_API_URL}/api/v1/contacts/{contact_id}",
            json=fields,
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()
