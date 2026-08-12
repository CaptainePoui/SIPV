import uuid
import asyncio
import wave
from pathlib import Path
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.core.database import get_db
from app.core.esl import get_esl, ESLClient
from app.api.v1.endpoints.auth import get_current_user, get_current_user_or_service
from app.models.prompt import AudioPrompt
from app.models.ivr import IVR, IVROption
from app.models.sip import TenantDID, SIPExtension
from app.models.dialplan import InboundRoute
from app.models.user import User

router = APIRouter()

# Meme convention que UPLOAD_DIR de voicemail.py (TASK-S023.16) -- chemin absolu
# du serveur ou tourne reellement le service (/home/sipv/sipv/backend, pas la
# copie locale sur ERPCRM, voir TASKSIPV.md TASK-S018.3).
UPLOAD_DIR = Path("/home/sipv/sipv/backend/uploads/audio_prompts")

# TASK-S055/TASK-029.2 : cache lisible par le process freeswitch (conf/ appartient
# a freeswitch:freeswitch, sipv ne peut pas y creer d'entree -- dossier cree
# manuellement une fois : sudo mkdir + chown sipv:sipv + chmod 755, PAS persistant
# via code/migration, voir TASKSIPV.md TASK-029.7).
PROMPT_CACHE_DIR = Path("/usr/local/freeswitch/conf/prompts_cache")


class AudioPromptOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    filename: str
    duration_seconds: int | None
    is_active: bool
    created_at: datetime


def _out(p: AudioPrompt) -> AudioPromptOut:
    return AudioPromptOut(
        id=p.id, tenant_id=p.tenant_id, name=p.name, filename=p.filename,
        duration_seconds=p.duration_seconds, is_active=p.is_active, created_at=p.created_at,
    )


@router.get("/tenant/{tenant_id}", response_model=list[AudioPromptOut])
async def list_prompts(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    result = await db.execute(select(AudioPrompt).where(AudioPrompt.tenant_id == tenant_id).order_by(AudioPrompt.name))
    return [_out(p) for p in result.scalars().all()]


@router.post("/tenant/{tenant_id}", response_model=AudioPromptOut, status_code=status.HTTP_201_CREATED)
async def upload_prompt(
    tenant_id: uuid.UUID, name: str = Form(...), file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db), user: User | None = Depends(get_current_user_or_service),
):
    """Upload d'une phrase/annonce -- conversion ffmpeg vers WAV PCM mono (format
    attendu par FreeSWITCH `playback`). TASK-029.14 (test) : ne force plus 8kHz
    (narrowband, "voix dans un foulard" rapporte par l'utilisateur) -- garde le
    taux d'echantillonnage source (24kHz pour une phrase Voicebox) et laisse
    FreeSWITCH resampler lui-meme au moment de la lecture sur un appel reel. Si
    le test sur poste reel echoue/degrade, revenir a -ar 8000 fixe et plutot
    garder 2 fichiers (qualite pour l'ecoute ERPCRM, 8kHz pour l'appel reel)."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    prompt_id = uuid.uuid4()
    raw_ext = Path(file.filename or "").suffix or ".tmp"
    raw_path = UPLOAD_DIR / f"{prompt_id}_raw{raw_ext}"
    content = await file.read()
    raw_path.write_bytes(content)

    filename = f"{prompt_id}.wav"
    dest = UPLOAD_DIR / filename
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", str(raw_path), "-ac", "1", "-acodec", "pcm_s16le", str(dest),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    raw_path.unlink(missing_ok=True)
    if proc.returncode != 0:
        raise HTTPException(status_code=400, detail=f"Conversion audio échouée (format non reconnu) : {stderr.decode(errors='replace')[:300]}")

    duration_seconds = None
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(dest),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    out, _ = await proc.communicate()
    try:
        duration_seconds = int(float(out.decode().strip()))
    except (ValueError, AttributeError):
        pass  # ffprobe absent ou sortie inattendue -- champ decoratif, pas bloquant

    p = AudioPrompt(id=prompt_id, tenant_id=tenant_id, name=name, filename=filename, duration_seconds=duration_seconds)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return _out(p)


@router.get("/{prompt_id}/file")
async def download_prompt(prompt_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    result = await db.execute(select(AudioPrompt).where(AudioPrompt.id == prompt_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Phrase introuvable")
    path = UPLOAD_DIR / p.filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Fichier introuvable sur le serveur")
    return FileResponse(path, filename=p.filename, media_type="audio/wav")


class AudioPromptUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None


@router.put("/{prompt_id}", response_model=AudioPromptOut)
async def update_prompt(prompt_id: uuid.UUID, payload: AudioPromptUpdate, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    result = await db.execute(select(AudioPrompt).where(AudioPrompt.id == prompt_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Phrase introuvable")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    await db.commit()
    await db.refresh(p)
    return _out(p)


async def _prompt_usages(prompt_id: uuid.UUID, db: AsyncSession) -> list[str]:
    """Liste lisible des endroits qui referencent encore cette phrase --
    sert a bloquer la suppression plutot que de laisser une reference orpheline
    (LOI robustesse : toujours pouvoir rediter, jamais de suppression qui casse
    silencieusement un IVR ou un DID deja configure)."""
    usages = []
    pid = str(prompt_id)

    result = await db.execute(select(IVR).where(IVR.greeting_prompt_id == prompt_id))
    for ivr in result.scalars().all():
        usages.append(f"Greeting de l'IVR « {ivr.name} »")

    result = await db.execute(select(TenantDID).where(TenantDID.destination_type == "message", TenantDID.destination == pid))
    for d in result.scalars().all():
        usages.append(f"Destination du DID {d.number}")
    result = await db.execute(select(TenantDID).where(TenantDID.after_message_destination_type == "message", TenantDID.after_message_destination == pid))
    for d in result.scalars().all():
        usages.append(f"2e destination (après message) du DID {d.number}")

    result = await db.execute(select(InboundRoute).where(InboundRoute.destination_type == "message", InboundRoute.destination == pid))
    for r in result.scalars().all():
        usages.append(f"Route entrante {r.did_number}")

    return usages


@router.delete("/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt(prompt_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    result = await db.execute(select(AudioPrompt).where(AudioPrompt.id == prompt_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Phrase introuvable")
    usages = await _prompt_usages(prompt_id, db)
    if usages:
        raise HTTPException(status_code=400, detail=f"Phrase encore utilisée : {', '.join(usages)}")
    path = UPLOAD_DIR / p.filename
    path.unlink(missing_ok=True)
    await db.delete(p)
    await db.commit()


def _copy_with_lead_silence(src: Path, dest: Path, lead_seconds: float = 1.0) -> None:
    """TASK-S055.3 : prefixe une seconde de silence avant la phrase dans le
    fichier copie vers le cache -- laisse le temps de porter le combine a
    l'oreille apres avoir decroche. Comportement PAR DEFAUT de toute ecoute
    d'enregistrement par appel (pas seulement les Phrases IVR) -- generique,
    lit le format reel du WAV source (peu importe son sample rate)."""
    with wave.open(str(src), "rb") as wf:
        params = wf.getparams()
        frames = wf.readframes(wf.getnframes())
    silence_frame_count = int(params.framerate * lead_seconds)
    silence = b"\x00" * (silence_frame_count * params.sampwidth * params.nchannels)
    with wave.open(str(dest), "wb") as out:
        out.setparams(params)
        out.writeframes(silence + frames)


class PromptCallPayload(BaseModel):
    extension_id: uuid.UUID


@router.post("/{prompt_id}/call")
async def call_prompt(
    prompt_id: uuid.UUID, payload: PromptCallPayload,
    db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service),
):
    """TASK-S055 (Mode 1) : sonne un poste et joue cette phrase des que ca decroche
    -- &playback FreeSWITCH direct (originate_app), pas de passage par le dialplan XML."""
    result = await db.execute(select(AudioPrompt).where(AudioPrompt.id == prompt_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Phrase introuvable")

    result = await db.execute(select(SIPExtension).where(SIPExtension.id == payload.extension_id))
    ext = result.scalar_one_or_none()
    if not ext:
        raise HTTPException(status_code=404, detail="Poste introuvable")
    if ext.tenant_id != p.tenant_id:
        raise HTTPException(status_code=400, detail="Le poste n'appartient pas au même tenant que la phrase")

    src = UPLOAD_DIR / p.filename
    if not src.exists():
        raise HTTPException(status_code=404, detail="Fichier introuvable sur le serveur")
    PROMPT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dest = PROMPT_CACHE_DIR / p.filename
    _copy_with_lead_silence(src, dest)
    dest.chmod(0o644)

    # TASK-S055.1 : internal.xml force TOUS les enregistrements SIP dans le
    # domaine unique "sipv", peu importe le tenant -- @{account_number} donne
    # USER_NOT_REGISTERED. L'unicite du poste reste garantie par le prefixe
    # du username (ex: t1001-102), pas par le domaine SIP.
    endpoint = f"user/{ext.username}@sipv"
    esl: ESLClient = await get_esl()
    await esl.originate_app(endpoint, "playback", str(dest))
    return {"ok": True}
