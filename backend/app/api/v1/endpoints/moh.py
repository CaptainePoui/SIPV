import uuid
import asyncio
import shutil
from pathlib import Path
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from pydantic import BaseModel
from app.core.database import get_db
from app.core.esl import get_esl, ESLClient
from app.api.v1.endpoints.auth import get_current_user_or_service
from app.models.moh import MohFile, TenantMohSelection
from app.models.sip import SIPExtension
from app.core.local_stream import regenerate_tenant_moh_stream
from app.models.user import User

router = APIRouter()

# Meme convention que prompts.py (TASK-S046) -- chemin absolu du serveur ou
# tourne reellement le service.
UPLOAD_DIR = Path("/home/sipv/sipv/backend/uploads/moh_files")

# TASK-S055/TASK-029.2 (meme pattern que prompts.py) : /home/sipv/ est en 750,
# freeswitch (autre utilisateur) ne peut pas y traverser -- confirme en direct
# (playback() echouait avec "Permission denied" sur un fichier pourtant
# lisible individuellement, la traversee du dossier parent bloquait tout).
# Dossier cree manuellement une fois : sudo mkdir + chown sipv:sipv + chmod 755,
# PAS persistant via code/migration.
MOH_CALL_CACHE_DIR = Path("/usr/local/freeswitch/conf/moh_call_cache")


class MohFileOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID | None
    name: str
    filename: str
    duration_seconds: int | None
    is_active: bool
    created_at: datetime


def _out(m: MohFile) -> MohFileOut:
    return MohFileOut(
        id=m.id, tenant_id=m.tenant_id, name=m.name, filename=m.filename,
        duration_seconds=m.duration_seconds, is_active=m.is_active, created_at=m.created_at,
    )


@router.get("", response_model=list[MohFileOut])
async def list_all_moh(db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    """Toutes les MOH (globales + dediees), pour la page Serveur (admin SIPV)."""
    result = await db.execute(select(MohFile).order_by(MohFile.name))
    return [_out(m) for m in result.scalars().all()]


@router.get("/available/tenant/{tenant_id}", response_model=list[MohFileOut])
async def list_available_moh(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    """MOH disponibles pour CE tenant : globales (tenant_id NULL) + dediees a
    lui. Utilise par la fiche compagnie pour construire la liste a cocher.
    Inclut aussi les fichiers desactives (is_active=False) -- affiches grises
    dans l'UI avec un bouton "Activer", sinon un fichier de base desactive
    n'aurait plus aucun moyen d'etre reactive depuis la fiche compagnie.
    is_active reste respecte separement dans regenerate_tenant_moh_stream
    (la generation reelle du flux local_stream, jamais un fichier inactif)."""
    result = await db.execute(
        select(MohFile).where(
            or_(MohFile.tenant_id == None, MohFile.tenant_id == tenant_id),  # noqa: E711
        ).order_by(MohFile.name)
    )
    return [_out(m) for m in result.scalars().all()]


@router.post("", response_model=MohFileOut, status_code=status.HTTP_201_CREATED)
async def upload_moh(
    name: str = Form(...), file: UploadFile = File(...), tenant_id: uuid.UUID | None = Form(None),
    db: AsyncSession = Depends(get_db), user: User | None = Depends(get_current_user_or_service),
):
    """Upload d'un fichier MOH -- tenant_id omis/null = global (visible par
    tous les tenants). Meme conversion ffmpeg que prompts.py/voicemail.py :
    n'importe quel format en entree, WAV PCM mono en sortie. TASK-029.14 : ne
    force plus 8kHz -- garde le taux source, FreeSWITCH resample a la lecture."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    moh_id = uuid.uuid4()
    raw_ext = Path(file.filename or "").suffix or ".tmp"
    raw_path = UPLOAD_DIR / f"{moh_id}_raw{raw_ext}"
    content = await file.read()
    raw_path.write_bytes(content)

    filename = f"{moh_id}.wav"
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
        pass

    m = MohFile(id=moh_id, tenant_id=tenant_id, name=name, filename=filename, duration_seconds=duration_seconds)
    db.add(m)
    await db.commit()
    await db.refresh(m)

    # Fichier global ou dedie : les tenants qui l'utilisent deja doivent le
    # voir apparaitre dans leur stream sans action manuelle. Best-effort --
    # ne bloque jamais l'upload si la regeneration echoue.
    await _regenerate_affected_tenants(m, db)

    return _out(m)


class MohFileUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    tenant_id: uuid.UUID | None = None
    clear_tenant: bool = False


@router.put("/{moh_id}", response_model=MohFileOut)
async def update_moh(moh_id: uuid.UUID, payload: MohFileUpdate, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    result = await db.execute(select(MohFile).where(MohFile.id == moh_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Fichier MOH introuvable")
    data = payload.model_dump(exclude_unset=True, exclude={"clear_tenant"})
    if payload.clear_tenant:
        m.tenant_id = None
        data.pop("tenant_id", None)
    for k, v in data.items():
        setattr(m, k, v)
    await db.commit()
    await db.refresh(m)
    await _regenerate_affected_tenants(m, db)
    return _out(m)


@router.get("/{moh_id}/file")
async def download_moh(moh_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    result = await db.execute(select(MohFile).where(MohFile.id == moh_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Fichier MOH introuvable")
    path = UPLOAD_DIR / m.filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Fichier introuvable sur le serveur")
    return FileResponse(path, filename=m.filename, media_type="audio/wav")


class MohCallPayload(BaseModel):
    extension_id: uuid.UUID


@router.post("/{moh_id}/call")
async def call_moh(
    moh_id: uuid.UUID, payload: MohCallPayload,
    db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service),
):
    """Meme principe que AudioPrompt.call (TASK-S055, prompts.py) : sonne un
    poste et joue ce fichier MOH des que ca decroche -- &playback FreeSWITCH
    direct (originate_app), pour l'ecouter au telephone avant de le choisir."""
    result = await db.execute(select(MohFile).where(MohFile.id == moh_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Fichier MOH introuvable")

    result = await db.execute(select(SIPExtension).where(SIPExtension.id == payload.extension_id))
    ext = result.scalar_one_or_none()
    if not ext:
        raise HTTPException(status_code=404, detail="Poste introuvable")
    if m.tenant_id is not None and ext.tenant_id != m.tenant_id:
        raise HTTPException(status_code=400, detail="Le poste n'appartient pas au même tenant que ce fichier MOH")

    src = UPLOAD_DIR / m.filename
    if not src.exists():
        raise HTTPException(status_code=404, detail="Fichier introuvable sur le serveur")
    MOH_CALL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dest = MOH_CALL_CACHE_DIR / m.filename
    shutil.copy2(src, dest)
    dest.chmod(0o644)

    endpoint = f"user/{ext.username}@sipv"
    esl: ESLClient = await get_esl()
    await esl.originate_app(endpoint, "playback", str(dest))
    return {"ok": True}


@router.delete("/{moh_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_moh(moh_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    result = await db.execute(select(MohFile).where(MohFile.id == moh_id))
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="Fichier MOH introuvable")
    sel_result = await db.execute(select(TenantMohSelection.tenant_id).where(TenantMohSelection.moh_file_id == moh_id))
    affected_tenants = [t for (t,) in sel_result.all()]
    path = UPLOAD_DIR / m.filename
    path.unlink(missing_ok=True)
    await db.delete(m)
    await db.commit()
    for tenant_id in affected_tenants:
        await regenerate_tenant_moh_stream(tenant_id, db)


# ── Sélection par tenant ─────────────────────────────────────────────────────

class MohSelectionItem(BaseModel):
    moh_file_id: uuid.UUID
    sort_order: int = 0


class MohSelectionOut(BaseModel):
    moh_file_id: uuid.UUID
    name: str
    sort_order: int


@router.get("/selection/tenant/{tenant_id}", response_model=list[MohSelectionOut])
async def get_selection(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    result = await db.execute(
        select(TenantMohSelection, MohFile.name)
        .join(MohFile, MohFile.id == TenantMohSelection.moh_file_id)
        .where(TenantMohSelection.tenant_id == tenant_id)
        .order_by(TenantMohSelection.sort_order)
    )
    return [MohSelectionOut(moh_file_id=sel.moh_file_id, name=name, sort_order=sel.sort_order) for sel, name in result.all()]


@router.put("/selection/tenant/{tenant_id}", response_model=list[MohSelectionOut])
async def set_selection(tenant_id: uuid.UUID, items: list[MohSelectionItem], db: AsyncSession = Depends(get_db), _: User | None = Depends(get_current_user_or_service)):
    """Remplace la sélection complète de ce tenant (liste ordonnée) --
    demande explicite : plusieurs fichiers sélectionnables, dans l'ordre."""
    existing = await db.execute(select(TenantMohSelection).where(TenantMohSelection.tenant_id == tenant_id))
    for row in existing.scalars().all():
        await db.delete(row)
    await db.flush()
    for i, item in enumerate(items):
        db.add(TenantMohSelection(tenant_id=tenant_id, moh_file_id=item.moh_file_id, sort_order=item.sort_order or i))
    await db.commit()

    await regenerate_tenant_moh_stream(tenant_id, db)

    result = await db.execute(
        select(TenantMohSelection, MohFile.name)
        .join(MohFile, MohFile.id == TenantMohSelection.moh_file_id)
        .where(TenantMohSelection.tenant_id == tenant_id)
        .order_by(TenantMohSelection.sort_order)
    )
    return [MohSelectionOut(moh_file_id=sel.moh_file_id, name=name, sort_order=sel.sort_order) for sel, name in result.all()]


async def _regenerate_affected_tenants(m: MohFile, db: AsyncSession) -> None:
    """Un fichier global affecte TOUS les tenants qui ont au moins une
    sélection active ; un fichier dédié n'affecte que son tenant."""
    if m.tenant_id:
        await regenerate_tenant_moh_stream(m.tenant_id, db)
        return
    result = await db.execute(select(TenantMohSelection.tenant_id).distinct())
    for (tenant_id,) in result.all():
        await regenerate_tenant_moh_stream(tenant_id, db)
