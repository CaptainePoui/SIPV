"""Migration de tenant (TASK-051 cote ERPCRM) : inventaire, apercu, execution. Appele par ERPCRM (cle de service) --
ecran ERPCRM -> Serveur -> Migration. Voir app/core/tenant_migration.py."""
import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user_or_service
from app.core import erpcrm_client, tenant_migration as tm
from app.core.database import get_db
from app.core.esl import get_esl
from app.models.audit_log import AuditLog
from app.models.user import User

router = APIRouter()
log = logging.getLogger("migration")


class Selection(BaseModel):
    source_tenant_id: uuid.UUID
    dest_tenant_id: uuid.UUID
    extensions: list[dict] = []        # [{"id": ..., "new_number": "..."}]
    dids: list[uuid.UUID] = []
    objects: dict[str, dict[str, str]] = {}   # {"ring_groups": {"<id>": "move|copy|leave"}, ...}
    e911: dict[str, uuid.UUID | None] = {}    # {"extension:<id>": e911_address_id, "did:<id>": ...}


def _sel(s: Selection) -> dict:
    return s.model_dump(mode="json")


@router.get("/tenant/{tenant_id}/inventory")
async def inventory(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    inv = await tm.inventory(db, tenant_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Tenant introuvable")
    return inv


@router.post("/preview")
async def preview(sel: Selection, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    return await tm.preview(db, _sel(sel))


@router.post("/execute")
async def execute(sel: Selection, request: Request, db: AsyncSession = Depends(get_db), user: User | None = Depends(get_current_user_or_service)):
    client_ip = request.client.host if request.client else "?"
    res = await tm.execute(db, _sel(sel))
    if not res.get("ok"):
        raise HTTPException(status_code=409, detail=res)
    src, dst = res["source"], res["dest"]
    after = []
    # Facturation : retrait dans l'ancien tenant, ajout dans le nouveau (best-effort, comme a la creation d'un poste)
    for e in res["moved_extensions"]:
        for tid, action in ((src["id"], "extension_removed"), (dst["id"], "extension_added")):
            try:
                await erpcrm_client.send_billing_event(tenant_id=tid, action=action, service_type="extension", service_ref=e["id"],
                                                       description=f"Poste {e['number']} — {e['name']}")
            except Exception as ex:
                after.append(f"Avis de facturation du poste {e['number']} non envoyé : {ex}")
    for d in res["moved_dids"]:
        for tid, action in ((src["id"], "did_removed"), (dst["id"], "did_added")):
            try:
                await erpcrm_client.send_billing_event(tenant_id=tid, action=action, service_type="did", service_ref=d["id"],
                                                       description=f"DID {d['number']}")
            except Exception as ex:
                after.append(f"Avis de facturation du numéro {d['number']} non envoyé : {ex}")
    # Musique d'attente des deux tenants
    if res["moh_changed"]:
        from app.core.local_stream import regenerate_tenant_moh_stream
        for tid in (src["id"], dst["id"]):
            try:
                await regenerate_tenant_moh_stream(uuid.UUID(tid), db)
            except Exception as ex:
                after.append(f"Musique d'attente non régénérée : {ex}")
    # Configuration rechargee, telephones des postes migres reprovisionnes (ils redemarrent et prennent le nouvel identifiant)
    try:
        esl = await get_esl()
        await esl.reload_xml()
        from app.core.phone_reboot import reboot_phones
        for e in res["moved_extensions"]:
            if not await reboot_phones(e["old_username"]):
                after.append(f"Poste {e['number']} : aucun téléphone enregistré sous {e['old_username']} — configurez {e['username']} sur l appareil.")
    except Exception as ex:
        after.append(f"FreeSWITCH : rechargement ou redémarrage des téléphones à faire à la main ({ex}).")
    try:
        db.add(AuditLog(tenant_id=uuid.UUID(dst["id"]), entity_type="tenant", entity_id=dst["id"],
                        entity_label=f"Migration {src['account_number']} -> {dst['account_number']}", action="update",
                        old_data={"source": src}, new_data={"dest": dst, "extensions": res["moved_extensions"],
                                                            "dids": res["moved_dids"], "backup": res["backup"],
                                                            "cdr_marked": res["cdr_marked"]},
                        changed_by=user.email if user else "ERPCRM", changed_by_ip=client_ip))
        await db.commit()
    except Exception as ex:
        log.warning("journal de migration non ecrit : %s", ex)
    return {**res, "after": after}
