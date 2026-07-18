from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError
from pydantic import BaseModel
from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_password, create_access_token, decode_token
from app.models.user import User

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    full_name: str
    role: str


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Identifiants invalides")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé")
    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return TokenResponse(access_token=token, user_id=str(user.id), full_name=user.full_name, role=user.role.value)


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalide")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")
    return user


async def get_current_user_or_service(
    token: str | None = Depends(oauth2_scheme_optional),
    x_api_key: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """
    Accepte soit un JWT utilisateur SIPV normal, soit la cle de service ERPCRM
    (X-Api-Key). Retourne un User pour un login normal, None pour un appel de service
    (ERPCRM). Utilise sur les endpoints qu'ERPCRM doit pouvoir appeler en proxy (fiche
    compagnie/contact) sans compte utilisateur SIPV.
    """
    if x_api_key:
        if not settings.ERPCRM_API_KEY or x_api_key != settings.ERPCRM_API_KEY:
            raise HTTPException(status_code=401, detail="Clé API invalide")
        return None
    if token:
        try:
            payload = decode_token(token)
            user_id = payload.get("sub")
        except JWTError:
            raise HTTPException(status_code=401, detail="Token invalide")
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Utilisateur introuvable")
        return user
    raise HTTPException(status_code=401, detail="Authentification requise")


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {"id": str(user.id), "email": user.email, "full_name": user.full_name, "role": user.role.value}
