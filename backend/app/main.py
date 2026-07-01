from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
import app.models
from app.api.v1.endpoints import auth, tenants, extensions, commit, sync, trunks, dids, routes, ivr, voicemail, cdr, e911, provisioning, recordings, fax, sms, security, webhooks, schedules


app = FastAPI(
    title="Simple IP SIPV",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3020", f"http://{settings.SIPV_HOST}:3020", f"http://{settings.ERPCRM_HOST}:3020"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(tenants.router, prefix="/api/v1/tenants", tags=["tenants"])
app.include_router(extensions.router, prefix="/api/v1/extensions", tags=["extensions"])
app.include_router(commit.router, prefix="/api/v1/changes", tags=["changes"])
app.include_router(sync.router, prefix="/api/v1/sync", tags=["sync"])
app.include_router(trunks.router, prefix="/api/v1/trunks", tags=["trunks"])
app.include_router(dids.router, prefix="/api/v1/dids", tags=["dids"])
app.include_router(routes.router, prefix="/api/v1/routes", tags=["routes"])
app.include_router(ivr.router, prefix="/api/v1/ivr", tags=["ivr"])
app.include_router(voicemail.router, prefix="/api/v1/voicemail", tags=["voicemail"])
app.include_router(cdr.router, prefix="/api/v1/cdr", tags=["cdr"])
app.include_router(e911.router, prefix="/api/v1/e911", tags=["e911"])
app.include_router(provisioning.router, prefix="/api/v1/provisioning", tags=["provisioning"])
app.include_router(recordings.router, prefix="/api/v1/recordings", tags=["recordings"])
app.include_router(fax.router, prefix="/api/v1/fax", tags=["fax"])
app.include_router(sms.router, prefix="/api/v1/sms", tags=["sms"])
app.include_router(security.router, prefix="/api/v1/security", tags=["security"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["webhooks"])
app.include_router(schedules.router, prefix="/api/v1/schedules", tags=["schedules"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "project": "Simple IP SIPV", "env": settings.ENVIRONMENT}
