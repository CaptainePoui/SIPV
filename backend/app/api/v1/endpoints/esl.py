"""
ESL endpoints — FreeSWITCH status and commands.
Used by Simple IP admin only (requires internal JWT auth).
"""
import json
import re
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.v1.endpoints.auth import get_current_user, get_current_user_or_service
from app.core.esl import get_esl, ESLClient
from app.models.user import User
from app.models.sip import SIPExtension
from app.models.tenant import Tenant
from app.models.security import BlockedIP
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
    registered: bool
    public_ip: str | None = None   # IP telle que vue par FreeSWITCH (network_ip) — la vraie IP publique du poste
    private_ip: str | None = None  # IP annoncee par le poste lui-meme dans son Contact SIP (souvent l'IP LAN)
    port: str | None = None
    registered_count: int = 0  # nombre d'appareils enregistres simultanement pour ce poste (TASK-S011.2)


def _parse_registrations(raw: str) -> dict[str, list[dict]]:
    """
    Parse la sortie de 'show registrations as json'.
    public_ip/private_ip identiques => SIP ALG actif ou double NAT chez le client
    (diagnostic reseau cote client, pas cote SIPV).
    Retourne une LISTE par username (un poste peut avoir plusieurs appareils
    enregistres simultanement si max_contacts > 1 -- TASK-S011.2) au lieu d'ecraser
    silencieusement les enregistrements multiples comme avant.
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    result: dict[str, list[dict]] = {}
    for row in data.get("rows", []):
        username = row.get("reg_user", "")
        if not username:
            continue
        url = row.get("url", "")
        m = re.search(r"@([0-9a-fA-F:.]+):", url)
        result.setdefault(username, []).append({
            "public_ip": row.get("network_ip"),
            "private_ip": m.group(1) if m else None,
            "port": row.get("network_port"),
        })
    return result


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
    _: User | None = Depends(get_current_user_or_service),
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
        raw = await esl.show_registrations()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"ESL error: {exc}")

    regs = _parse_registrations(raw)
    out = []
    for ext in extensions:
        reg_list = regs.get(ext.username, [])
        reg = reg_list[0] if reg_list else None
        out.append(RegistrationOut(
            username=ext.username,
            registered=reg is not None,
            public_ip=reg["public_ip"] if reg else None,
            private_ip=reg["private_ip"] if reg else None,
            port=reg["port"] if reg else None,
            registered_count=len(reg_list),
        ))
    return out


@router.get("/registration/{username}")
async def extension_registration(username: str, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    """
    Check if a single SIP extension is currently registered (+ combien d'appareils).
    ⚠️ Bug corrige (TASK-S011.2, pre-existant depuis TASK-S018) : `sofia_contact` a
    besoin de "user@domain", pas juste "user" -- sans le domaine, FreeSWITCH repond
    systematiquement "error/user_not_registered" meme quand le poste EST enregistre
    (verifie : `sofia_contact internal/t1001-100` echoue, `.../t1001-100@t1001`
    fonctionne). Le domaine = le tenant.account_number (meme valeur que le prefixe
    du username), recupere via une vraie requete DB plutot que de parser la string.
    """
    ext_result = await db.execute(select(SIPExtension).where(SIPExtension.username == username))
    ext = ext_result.scalar_one_or_none()
    domain = None
    if ext:
        tenant = await db.get(Tenant, ext.tenant_id)
        domain = tenant.account_number if tenant else None
    lookup = f"{username}@{domain}" if domain else username
    try:
        esl: ESLClient = await get_esl()
        contact = await esl.sofia_contact("internal", lookup)
        registered = bool(contact and "error" not in contact.lower() and contact.strip())
        registered_count = 0
        public_ip = None
        is_blocked = False
        if registered:
            raw = await esl.show_registrations()
            reg_list = _parse_registrations(raw).get(username, [])
            registered_count = len(reg_list)
            public_ip = reg_list[0]["public_ip"] if reg_list else None
            if public_ip:
                blocked_result = await db.execute(
                    select(BlockedIP).where(
                        BlockedIP.ip_address == public_ip,
                        (BlockedIP.expires_at.is_(None)) | (BlockedIP.expires_at > datetime.now(timezone.utc)),
                    )
                )
                is_blocked = blocked_result.scalar_one_or_none() is not None
        return {
            "username": username, "contact": contact, "registered": registered,
            "registered_count": registered_count, "public_ip": public_ip, "is_blocked": is_blocked,
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"ESL error: {exc}")


# ── Monitoring poste temps reel (TASK-S020.2) ───────────────────────────────────

def _parse_sofia_reg_detail(raw: str) -> dict[str, dict]:
    """
    Parse 'sofia status profile <p> reg' (texte, PAS json -- ces champs n'existent
    pas dans 'show registrations as json'). Retourne par Auth-User : Ping-Status,
    Ping-Time (ms), EXPSECS (secondes avant expiration -- indique indirectement
    depuis quand le dernier keep-alive/register a eu lieu).
    """
    result: dict[str, dict] = {}
    for block in raw.split("\n\n"):
        fields: dict[str, str] = {}
        for line in block.splitlines():
            m = re.match(r"^([\w-]+):\s+(.*)$", line.strip())
            if m:
                fields[m.group(1)] = m.group(2).strip()
        auth_user = fields.get("Auth-User")
        if not auth_user:
            continue
        expsecs_m = re.search(r"EXPSECS\((\d+)\)", fields.get("Status", ""))
        result[auth_user] = {
            "ping_status": fields.get("Ping-Status"),
            "ping_time_ms": float(fields["Ping-Time"]) if fields.get("Ping-Time") else None,
            "expires_in_seconds": int(expsecs_m.group(1)) if expsecs_m else None,
        }
    return result


class CallQualityOut(BaseModel):
    active_call: bool
    mos: float | None = None            # qualite audio (1-5, 5=excellent) -- mod_spandsp/RTCP-XR
    jitter_ms: float | None = None
    packet_loss_percent: float | None = None


class MonitoringOut(BaseModel):
    username: str
    ping_status: str | None
    ping_time_ms: float | None
    expires_in_seconds: int | None
    call_quality: CallQualityOut
    last_sip_error_code: str | None = None  # ⚠️ toujours null -- voir note dans TASKSIPV.md


async def _active_call_uuid(esl: ESLClient, username: str) -> str | None:
    """Cherche un appel actif impliquant ce username. Retourne le Unique-ID ou None."""
    try:
        raw = await esl.show_channels()
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    for row in data.get("rows", []):
        cid_num = row.get("cid_num", "") or ""
        dest_num = row.get("dest", "") or ""
        if username in cid_num or username in dest_num:
            return row.get("uuid")
    return None


@router.get("/monitoring/{username}", response_model=MonitoringOut)
async def get_monitoring(username: str, _: User = Depends(get_current_user)):
    """
    Monitoring temps reel d'un poste (TASK-S020.2).
    ⚠️ Ce qui EST reel : ping-status/ping-time/expires_in_seconds (donnees FreeSWITCH
    existantes, exposees pour la premiere fois ici) et la qualite d'appel SI un appel
    est actif en ce moment (lue via uuid_getvar sur les variables RTP du canal -- vide
    si aucun appel en cours, ce qui est le cas normal la plupart du temps).
    ⚠️ Ce qui n'est PAS fait : historique persistant (aucune table de serie temporelle
    -- ajouter reviendrait a stocker des lectures ponctuelles sans avoir un worker qui
    interroge regulierement, pas construit ici) ; dernier code erreur SIP (401/403/...)
    -- necessiterait de capturer les evenements d'echec SIP au moment ou ils arrivent,
    rien ne le fait actuellement (meme lacune deja documentee pour S014.2).
    """
    try:
        esl: ESLClient = await get_esl()
        raw = await esl.sofia_status_profile_reg("internal")
        detail = _parse_sofia_reg_detail(raw).get(username, {})

        quality = CallQualityOut(active_call=False)
        call_uuid = await _active_call_uuid(esl, username)
        if call_uuid:
            mos_raw = await esl.uuid_getvar(call_uuid, "rtp_audio_in_mos")
            jitter_raw = await esl.uuid_getvar(call_uuid, "rtp_audio_in_jitter_min_variance")
            loss_raw = await esl.uuid_getvar(call_uuid, "rtp_audio_in_skip_packet_count")
            quality = CallQualityOut(
                active_call=True,
                mos=float(mos_raw) if mos_raw and mos_raw.replace(".", "", 1).isdigit() else None,
                jitter_ms=float(jitter_raw) if jitter_raw and jitter_raw.replace(".", "", 1).isdigit() else None,
                packet_loss_percent=float(loss_raw) if loss_raw and loss_raw.isdigit() else None,
            )

        return MonitoringOut(
            username=username,
            ping_status=detail.get("ping_status"),
            ping_time_ms=detail.get("ping_time_ms"),
            expires_in_seconds=detail.get("expires_in_seconds"),
            call_quality=quality,
        )
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
