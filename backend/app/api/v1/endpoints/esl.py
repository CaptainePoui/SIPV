"""
ESL endpoints — FreeSWITCH status and commands.
Used by Simple IP admin only (requires internal JWT auth).
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.v1.endpoints.auth import get_current_user
from app.core.esl import get_esl, ESLClient
from app.models.user import User
from app.models.sip import SIPExtension
from app.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

router = APIRouter()


class ESLStatusOut(BaseModel):
    connected: bool
    sofia_status: str | None = None
    error: str | None = None


class RegistrationOut(BaseModel):
    username: str
    contact: str
    registered: bool


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/status", response_model=ESLStatusOut)
async def esl_status(_: User = Depends(get_current_user)):
    """FreeSWITCH ESL connection status + sofia profile overview."""
    try:
        esl = await get_esl()
        sofia = await esl.sofia_status()
        return ESLStatusOut(connected=True, sofia_status=sofia)
    except Exception as exc:
        return ESLStatusOut(connected=False, error=str(exc))


# ── Reload ────────────────────────────────────────────────────────────────────

@router.post("/reload")
async def reload_xml(_: User = Depends(get_current_user)):
    """
    Tell FreeSWITCH to reload its XML configuration.
    Use after committing changes so mod_xml_curl cache is invalidated.
    """
    try:
        esl: ESLClient = await get_esl()
        result = await esl.reload_xml()
        return {"result": result}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"ESL error: {exc}")


# ── Registrations ─────────────────────────────────────────────────────────────

@router.get("/registrations")
async def all_registrations(_: User = Depends(get_current_user)):
    """List all currently registered SIP endpoints (all tenants)."""
    try:
        esl: ESLClient = await get_esl()
        result = await esl.show_registrations()
        return {"raw": result}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"ESL error: {exc}")


@router.get("/registrations/tenant/{tenant_id}", response_model=list[RegistrationOut])
async def tenant_registrations(
    tenant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Check registration status for every extension of a tenant.
    Returns one entry per extension: registered or not.
    """
    result = await db.execute(
        select(SIPExtension).where(
            SIPExtension.tenant_id == tenant_id,
            SIPExtension.is_active == True,
        )
    )
    extensions = result.scalars().all()
    if not extensions:
        return []

    try:
        esl: ESLClient = await get_esl()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"ESL error: {exc}")

    out = []
    for ext in extensions:
        contact = await esl.sofia_contact("internal", ext.username)
        out.append(RegistrationOut(
            username=ext.username,
            contact=contact,
            registered=bool(contact and "error" not in contact.lower() and contact.strip()),
        ))
    return out


@router.get("/registration/{username}")
async def extension_registration(username: str, _: User = Depends(get_current_user)):
    """Check if a single SIP extension is currently registered."""
    try:
        esl: ESLClient = await get_esl()
        contact = await esl.sofia_contact("internal", username)
        registered = bool(contact and "error" not in contact.lower() and contact.strip())
        return {"username": username, "contact": contact, "registered": registered}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"ESL error: {exc}")


# ── Call control ──────────────────────────────────────────────────────────────

@router.delete("/calls/{call_uuid}")
async def hangup_call(call_uuid: str, _: User = Depends(get_current_user)):
    """Hang up an active call by FreeSWITCH UUID."""
    try:
        esl: ESLClient = await get_esl()
        result = await esl.uuid_kill(call_uuid)
        return {"result": result}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"ESL error: {exc}")
