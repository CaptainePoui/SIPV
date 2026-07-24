import uuid
import secrets
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.voicemail import VoicemailBox, VoicemailMessage
from app.models.pending_change import PendingChange
from app.models.tenant import Tenant
from app.models.settings import TelephonySettings
from app.models.user import User

router = APIRouter()

# Meme convention que ERPCRM (backend/uploads/catalogue) -- chemin absolu du serveur
# ou tourne reellement le service (voir TASKSIPV.md TASK-S018.3 pour le rappel
# d'architecture : /home/sipv/sipv/backend, pas la copie locale sur ERPCRM).
UPLOAD_DIR = Path("/home/sipv/sipv/backend/uploads/voicemail_greetings")
GREETING_TYPES = {"unavailable", "busy", "name", "temp"}


async def _global_settings(db: AsyncSession) -> TelephonySettings:
    result = await db.execute(select(TelephonySettings))
    settings = result.scalar_one_or_none()
    if not settings:
        # Filet de securite si la ligne singleton a ete supprimee par erreur --
        # ne devrait pas arriver (creee par la migration 0022), mais ne pas planter.
        settings = TelephonySettings()
        db.add(settings)
        await db.flush()
    return settings


def _resolve_delete_after_email(box: VoicemailBox, tenant: Tenant, global_settings: TelephonySettings) -> bool:
    """
    Poste -> Compagnie -> Global. Pas via resolve_setting() generique : le nom de
    colonne differe volontairement sur Tenant (prefixe voicemail_ pour eviter
    l'ambiguite sur un modele partage) donc une resolution explicite est plus claire
    ici qu'un getattr uniforme.
    """
    if box.delete_after_email is not None:
        return box.delete_after_email
    if tenant.voicemail_delete_after_email is not None:
        return tenant.voicemail_delete_after_email
    return global_settings.voicemail_delete_after_email


class GlobalVoicemailSettingsOut(BaseModel):
    voicemail_delete_after_email: bool
    voicemail_max_messages: int
    voicemail_max_message_length: int
    voicemail_language: str

class GlobalVoicemailSettingsUpdate(BaseModel):
    voicemail_delete_after_email: bool | None = None
    voicemail_max_messages: int | None = None
    voicemail_max_message_length: int | None = None
    voicemail_language: str | None = None


@router.get("/global-settings", response_model=GlobalVoicemailSettingsOut)
async def get_global_settings(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    s = await _global_settings(db)
    return GlobalVoicemailSettingsOut(
        voicemail_delete_after_email=s.voicemail_delete_after_email,
        voicemail_max_messages=s.voicemail_max_messages,
        voicemail_max_message_length=s.voicemail_max_message_length,
        voicemail_language=s.voicemail_language,
    )


@router.put("/global-settings", response_model=GlobalVoicemailSettingsOut)
async def update_global_settings(payload: GlobalVoicemailSettingsUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    s = await _global_settings(db)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    await db.commit()
    await db.refresh(s)
    return GlobalVoicemailSettingsOut(
        voicemail_delete_after_email=s.voicemail_delete_after_email,
        voicemail_max_messages=s.voicemail_max_messages,
        voicemail_max_message_length=s.voicemail_max_message_length,
        voicemail_language=s.voicemail_language,
    )


class VoicemailOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    extension_id: uuid.UUID | None
    mailbox: str
    context: str
    fullname: str
    email: str | None
    email_on_new: bool
    attach_message: bool
    delete_after_email: bool | None  # null = herite (voir effective_delete_after_email)
    effective_delete_after_email: bool
    max_messages: int
    max_message_length: int
    is_active: bool
    created_at: datetime
    language: str
    transcription_enabled: bool
    temp_greeting_enabled: bool
    has_greeting_unavailable: bool
    has_greeting_busy: bool
    has_greeting_name: bool
    has_greeting_temp: bool

class VoicemailCreate(BaseModel):
    extension_id: uuid.UUID | None = None
    mailbox: str
    fullname: str
    email: str | None = None
    password: str | None = None
    email_on_new: bool = True
    attach_message: bool = True
    delete_after_email: bool | None = None
    max_messages: int = 100
    max_message_length: int = 300
    context: str = "default"
    language: str = "fr"
    transcription_enabled: bool = False
    temp_greeting_enabled: bool = False

class VoicemailUpdate(BaseModel):
    fullname: str | None = None
    email: str | None = None
    password: str | None = None
    email_on_new: bool | None = None
    attach_message: bool | None = None
    delete_after_email: bool | None = None
    max_messages: int | None = None
    max_message_length: int | None = None
    is_active: bool | None = None
    language: str | None = None
    transcription_enabled: bool | None = None
    temp_greeting_enabled: bool | None = None

class VoicemailMessageOut(BaseModel):
    id: uuid.UUID
    msgnum: int
    folder: str
    callerid: str | None
    duration: int | None
    is_read: bool
    created_at: datetime


async def _out(v: VoicemailBox, db: AsyncSession) -> VoicemailOut:
    tenant = await db.get(Tenant, v.tenant_id)
    global_settings = await _global_settings(db)
    return VoicemailOut(
        id=v.id, tenant_id=v.tenant_id, extension_id=v.extension_id, mailbox=v.mailbox,
        context=v.context, fullname=v.fullname, email=v.email, email_on_new=v.email_on_new,
        attach_message=v.attach_message, delete_after_email=v.delete_after_email,
        effective_delete_after_email=_resolve_delete_after_email(v, tenant, global_settings),
        max_messages=v.max_messages, max_message_length=v.max_message_length,
        is_active=v.is_active, created_at=v.created_at,
        language=v.language, transcription_enabled=v.transcription_enabled,
        temp_greeting_enabled=v.temp_greeting_enabled,
        has_greeting_unavailable=bool(v.greeting_unavailable_path),
        has_greeting_busy=bool(v.greeting_busy_path),
        has_greeting_name=bool(v.greeting_name_path),
        has_greeting_temp=bool(v.greeting_temp_path),
    )


@router.get("/tenant/{tenant_id}", response_model=list[VoicemailOut])
async def list_voicemails(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(select(VoicemailBox).where(VoicemailBox.tenant_id == tenant_id).order_by(VoicemailBox.mailbox))
    return [await _out(v, db) for v in result.scalars().all()]


@router.post("/tenant/{tenant_id}", response_model=VoicemailOut, status_code=status.HTTP_201_CREATED)
async def create_voicemail(tenant_id: uuid.UUID, payload: VoicemailCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    password = payload.password or str(secrets.randbelow(9000) + 1000)
    data = payload.model_dump()
    data.pop("password", None)
    v = VoicemailBox(tenant_id=tenant_id, password=password, **data)
    db.add(v)
    db.add(PendingChange(tenant_id=tenant_id, change_type="add_voicemail", entity_type="voicemail",
                         payload={"mailbox": payload.mailbox, "context": payload.context, "email": payload.email},
                         created_by=user.email))
    await db.commit()
    await db.refresh(v)
    return await _out(v, db)


@router.put("/{vm_id}", response_model=VoicemailOut)
async def update_voicemail(vm_id: uuid.UUID, payload: VoicemailUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(VoicemailBox).where(VoicemailBox.id == vm_id))
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="Boîte vocale introuvable")
    data = payload.model_dump(exclude_unset=True)
    for k, val in data.items():
        setattr(v, k, val)
    db.add(PendingChange(tenant_id=v.tenant_id, change_type="update_voicemail", entity_type="voicemail",
                         entity_id=str(vm_id), payload={k: str(v) for k, v in data.items()}, created_by=user.email))
    await db.commit()
    await db.refresh(v)
    return await _out(v, db)


@router.delete("/{vm_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_voicemail(vm_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(VoicemailBox).where(VoicemailBox.id == vm_id))
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="Boîte vocale introuvable")
    db.add(PendingChange(tenant_id=v.tenant_id, change_type="remove_voicemail", entity_type="voicemail",
                         entity_id=str(vm_id), payload={"mailbox": v.mailbox}, created_by=user.email))
    await db.delete(v)
    await db.commit()


_GREETING_FIELD = {
    "unavailable": "greeting_unavailable_path",
    "busy": "greeting_busy_path",
    "name": "greeting_name_path",
    "temp": "greeting_temp_path",
}


@router.post("/{vm_id}/greetings/{greeting_type}", response_model=VoicemailOut)
async def upload_greeting(
    vm_id: uuid.UUID, greeting_type: str, file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    if greeting_type not in GREETING_TYPES:
        raise HTTPException(status_code=400, detail=f"Type d'accueil invalide (attendu: {', '.join(GREETING_TYPES)})")
    result = await db.execute(select(VoicemailBox).where(VoicemailBox.id == vm_id))
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="Boîte vocale introuvable")

    # TASK-023.16 : importer dans n'importe quel format, conversion automatique vers
    # le format attendu par FreeSWITCH (WAV PCM 8kHz mono, meme convention que les
    # enregistrements d'appels TASK-023.4). ffmpeg installe sur ce serveur (apt,
    # universe Ubuntu, meme principe que kamailio/rtpengine -- aucun depot tiers).
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    raw_ext = Path(file.filename or "").suffix or ".tmp"
    raw_path = UPLOAD_DIR / f"{vm_id}_{greeting_type}_raw{raw_ext}"
    content = await file.read()
    raw_path.write_bytes(content)

    filename = f"{vm_id}_{greeting_type}.wav"
    dest = UPLOAD_DIR / filename
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", str(raw_path), "-ar", "8000", "-ac", "1", "-acodec", "pcm_s16le", str(dest),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    raw_path.unlink(missing_ok=True)
    if proc.returncode != 0:
        raise HTTPException(status_code=400, detail=f"Conversion audio échouée (format non reconnu) : {stderr.decode(errors='replace')[:300]}")

    setattr(v, _GREETING_FIELD[greeting_type], filename)
    db.add(PendingChange(tenant_id=v.tenant_id, change_type="update_voicemail", entity_type="voicemail",
                         entity_id=str(vm_id), payload={"greeting_uploaded": greeting_type}, created_by=user.email))
    await db.commit()
    await db.refresh(v)
    return await _out(v, db)


@router.get("/{vm_id}/greetings/{greeting_type}")
async def download_greeting(vm_id: uuid.UUID, greeting_type: str, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    if greeting_type not in GREETING_TYPES:
        raise HTTPException(status_code=400, detail=f"Type d'accueil invalide (attendu: {', '.join(GREETING_TYPES)})")
    result = await db.execute(select(VoicemailBox).where(VoicemailBox.id == vm_id))
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="Boîte vocale introuvable")
    filename = getattr(v, _GREETING_FIELD[greeting_type])
    if not filename:
        raise HTTPException(status_code=404, detail="Aucun accueil uploadé pour ce type")
    path = UPLOAD_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Fichier introuvable sur le serveur")
    return FileResponse(path, filename=filename)


@router.delete("/{vm_id}/greetings/{greeting_type}", response_model=VoicemailOut)
async def delete_greeting(vm_id: uuid.UUID, greeting_type: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if greeting_type not in GREETING_TYPES:
        raise HTTPException(status_code=400, detail=f"Type d'accueil invalide (attendu: {', '.join(GREETING_TYPES)})")
    result = await db.execute(select(VoicemailBox).where(VoicemailBox.id == vm_id))
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="Boîte vocale introuvable")
    filename = getattr(v, _GREETING_FIELD[greeting_type])
    if filename:
        path = UPLOAD_DIR / filename
        if path.exists():
            path.unlink()
        setattr(v, _GREETING_FIELD[greeting_type], None)
        await db.commit()
        await db.refresh(v)
    return await _out(v, db)


@router.get("/{vm_id}/messages", response_model=list[VoicemailMessageOut])
async def list_messages(vm_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    result = await db.execute(
        select(VoicemailMessage).where(VoicemailMessage.mailbox_id == vm_id).order_by(VoicemailMessage.created_at.desc())
    )
    msgs = result.scalars().all()
    return [VoicemailMessageOut(id=m.id, msgnum=m.msgnum, folder=m.folder, callerid=m.callerid,
                                duration=m.duration, is_read=m.is_read, created_at=m.created_at)
            for m in msgs]
