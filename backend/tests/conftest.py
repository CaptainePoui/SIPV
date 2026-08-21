"""
Fixtures pytest pour SIPV.

Garde-fou obligatoire (Philippe, 2026-08-19, suite a l'incident SQL manuel
sur prod du 2026-08-14) : les tests ne doivent JAMAIS pouvoir toucher la DB
de dev/prod, meme par accident -- verifie au chargement de ce module, avant
qu'aucun test ne s'execute.
"""
import re
import uuid

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models.tenant import Tenant

TEST_DB_URL = settings.TEST_DATABASE_URL

if TEST_DB_URL == settings.DATABASE_URL or not re.search(r"_test\b", TEST_DB_URL):
    raise RuntimeError(
        "Garde-fou tests : TEST_DATABASE_URL doit pointer vers une base dont "
        "le nom contient '_test' et etre different de DATABASE_URL. "
        f"TEST_DATABASE_URL actuel : {TEST_DB_URL!r}. Verifie app/core/config.py "
        "et/ou la variable d'environnement avant de relancer les tests -- "
        "objectif : ne JAMAIS pouvoir executer les tests contre la DB de dev/prod."
    )

test_engine = create_async_engine(TEST_DB_URL, echo=False, poolclass=NullPool)


@pytest_asyncio.fixture
async def db_session():
    """
    Une transaction par test, annulee a la fin -- meme si le code sous test
    (ou un futur endpoint FastAPI) appelle session.commit(), SQLAlchemy
    convertit ca en SAVEPOINT (join_transaction_mode="create_savepoint") et
    la transaction de connexion externe reste annulable. sipv_test ne
    contient donc jamais de residu d'un test a l'autre.
    """
    async with test_engine.connect() as connection:
        trans = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()


async def make_tenant(db_session: AsyncSession, account_number: str | None = None) -> Tenant:
    """Tenant minimal valide pour les tests -- account_number aleatoire par defaut pour eviter les collisions entre tests paralleles."""
    tenant = Tenant(
        account_number=account_number or f"t{uuid.uuid4().hex[:10]}",
        company_name="Test Company",
        context_prefix="test",
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


async def make_api_client(db_session: AsyncSession):
    """
    Client HTTP reel contre l'app FastAPI, pas un appel direct aux fonctions
    Python -- passe par le vrai routing/dependances/validation Pydantic.
    get_db est surcharge pour utiliser LA MEME session que le test (donc la
    meme transaction, annulee a la fin par db_session) ; l'auth est
    surchargee pour eviter d'avoir a fabriquer un vrai JWT en test.
    """
    import httpx

    from app.core.database import get_db
    from app.main import app
    from app.api.v1.endpoints.auth import get_current_user, get_current_user_or_service
    from app.models.user import User, UserRole

    fake_user = User(email="tests@sipv.local", full_name="Test Runner", hashed_password="x", role=UserRole.admin)

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_current_user_or_service] = lambda: fake_user

    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    return client


@pytest_asyncio.fixture
async def api_client(db_session):
    client = await make_api_client(db_session)
    try:
        yield client
    finally:
        await client.aclose()
        from app.main import app
        app.dependency_overrides.clear()
