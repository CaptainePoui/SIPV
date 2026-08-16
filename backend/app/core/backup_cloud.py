"""Backup cloud infra SIPV (TASK-S059) -- OAuth + upload throttle pour Dropbox
et Google Drive. Meme convention que google_calendar.py pour le degrade
silencieux, mais credentials app (client_id/secret) resolues PAR CONNEXION
(DB, saisies dans Admin) avec fallback sur .env -- logiciel destine a etre
revendu a d'autres clients (interconnecteurs de lignes SIP), chaque
deploiement doit pouvoir connecter son propre Dropbox/Google Drive sans
jamais toucher au serveur (pas d'acces SSH/.env requis pour le client).

Bande passante : Dropbox et Google Drive n'offrent pas de throttling natif
cote client -- implemente ici par decoupage en chunks + pause calculee entre
chaque envoi (bandwidth_limit_kbps sur CloudBackupConnection)."""
import json
import time
import logging
from pathlib import Path
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.core.crypto import decrypt

log = logging.getLogger("backup_cloud")

BACKUP_FOLDER_NAME = "SIPV_Backups"
_CHUNK_SIZE = 4 * 1024 * 1024  # 4 MiB


def resolve_credentials(connection) -> tuple[str, str]:
    """client_id/secret saisis dans Admin (connection) sinon fallback .env du
    serveur (pratique pour notre propre instance ERPCRM, optionnel pour un
    client qui achete le logiciel et configure tout depuis l'UI)."""
    if connection.provider == "dropbox":
        default_id, default_secret = settings.DROPBOX_CLIENT_ID, settings.DROPBOX_CLIENT_SECRET
    else:
        default_id, default_secret = settings.GOOGLE_CLIENT_ID, settings.GOOGLE_CLIENT_SECRET
    client_id = connection.client_id or default_id
    client_secret = decrypt(connection.client_secret_enc) if connection.client_secret_enc else default_secret
    return client_id, client_secret


def _check_dropbox(r: httpx.Response):
    """raise_for_status() seul n'expose pas le corps de la reponse Dropbox
    (raison exacte du 4xx) ni le request-id utile pour le support Dropbox --
    on les capture explicitement dans le message d'erreur (visible dans
    BackupRunLog.error_message)."""
    if r.status_code >= 400:
        req_id = r.headers.get("X-Dropbox-Request-Id", "?")
        raise RuntimeError(f"Dropbox HTTP {r.status_code} (request-id={req_id}): {r.text[:1500]}")


def _sleep_for_chunk(nbytes: int, bandwidth_limit_kbps: int | None):
    if not bandwidth_limit_kbps:
        return
    expected_seconds = nbytes / 1024 / bandwidth_limit_kbps
    if expected_seconds > 0:
        time.sleep(expected_seconds)


# ── Dropbox ──────────────────────────────────────────────────────────────

# Demandes EXPLICITEMENT dans l'URL d'autorisation -- ne pas compter
# uniquement sur les cases cochees dans App Console > Permissions, qui
# n'affectent que les demandes SANS parametre scope explicite et peuvent
# preter a confusion sur l'etat reel du token emis.
DROPBOX_SCOPES = "account_info.read files.metadata.read files.content.read files.content.write"


def dropbox_authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "token_access_type": "offline",
        "scope": DROPBOX_SCOPES,
        "state": state,
    }
    return "https://www.dropbox.com/oauth2/authorize?" + urlencode(params)


async def dropbox_exchange_code(client_id: str, client_secret: str, code: str, redirect_uri: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post("https://api.dropboxapi.com/oauth2/token", data={
            "code": code,
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        })
    r.raise_for_status()
    return r.json()


async def _dropbox_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post("https://api.dropboxapi.com/oauth2/token", data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        })
    r.raise_for_status()
    return r.json()["access_token"]


async def dropbox_account_email(client_id: str, client_secret: str, refresh_token: str) -> str | None:
    access_token = await _dropbox_access_token(client_id, client_secret, refresh_token)
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            "https://api.dropboxapi.com/2/users/get_current_account",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if r.status_code != 200:
        return None
    return r.json().get("email")


async def dropbox_upload(client_id: str, client_secret: str, refresh_token: str, local_path: Path, remote_filename: str, bandwidth_limit_kbps: int | None = None) -> str:
    """Upload en session (start/append/finish) pour permettre le throttling
    par chunk. Retourne le chemin distant final."""
    access_token = await _dropbox_access_token(client_id, client_secret, refresh_token)
    remote_path = f"/{BACKUP_FOLDER_NAME}/{remote_filename}"
    data = local_path.read_bytes()
    size = len(data)
    log.info("dropbox_upload %s: taille fichier=%d octets, chunk=%d octets", remote_filename, size, _CHUNK_SIZE)

    async with httpx.AsyncClient(timeout=60) as client:
        if size <= _CHUNK_SIZE:
            r = await client.post(
                "https://content.dropboxapi.com/2/files/upload",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Dropbox-API-Arg": json.dumps({"path": remote_path, "mode": "overwrite"}),
                    "Content-Type": "application/octet-stream",
                },
                content=data,
            )
            _check_dropbox(r)
            _sleep_for_chunk(size, bandwidth_limit_kbps)
            return remote_path

        offset = 0
        first_chunk = data[:_CHUNK_SIZE]
        r = await client.post(
            "https://content.dropboxapi.com/2/files/upload_session/start",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/octet-stream"},
            content=first_chunk,
        )
        _check_dropbox(r)
        session_id = r.json()["session_id"]
        _sleep_for_chunk(len(first_chunk), bandwidth_limit_kbps)
        offset += len(first_chunk)

        while offset < size:
            chunk = data[offset:offset + _CHUNK_SIZE]
            is_last = (offset + len(chunk)) >= size
            cursor = {"session_id": session_id, "offset": offset}
            if is_last:
                r = await client.post(
                    "https://content.dropboxapi.com/2/files/upload_session/finish",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Dropbox-API-Arg": json.dumps({
                            "cursor": cursor,
                            "commit": {"path": remote_path, "mode": "overwrite"},
                        }),
                        "Content-Type": "application/octet-stream",
                    },
                    content=chunk,
                )
            else:
                r = await client.post(
                    "https://content.dropboxapi.com/2/files/upload_session/append_v2",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Dropbox-API-Arg": json.dumps({"cursor": cursor}),
                        "Content-Type": "application/octet-stream",
                    },
                    content=chunk,
                )
            _check_dropbox(r)
            _sleep_for_chunk(len(chunk), bandwidth_limit_kbps)
            offset += len(chunk)

    return remote_path


async def dropbox_list_backups(client_id: str, client_secret: str, refresh_token: str) -> list[dict]:
    access_token = await _dropbox_access_token(client_id, client_secret, refresh_token)
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            "https://api.dropboxapi.com/2/files/list_folder",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"path": f"/{BACKUP_FOLDER_NAME}"},
        )
    if r.status_code != 200:
        return []
    return [e for e in r.json().get("entries", []) if e.get(".tag") == "file"]


async def dropbox_delete(client_id: str, client_secret: str, refresh_token: str, remote_path: str):
    access_token = await _dropbox_access_token(client_id, client_secret, refresh_token)
    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(
            "https://api.dropboxapi.com/2/files/delete_v2",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"path": remote_path},
        )


# ── Google Drive ─────────────────────────────────────────────────────────

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"


def google_drive_authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": DRIVE_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)


async def google_drive_exchange_code(client_id: str, client_secret: str, code: str, redirect_uri: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post("https://oauth2.googleapis.com/token", data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        })
    r.raise_for_status()
    return r.json()


def _drive_service(client_id: str, client_secret: str, refresh_token: str):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        None,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
        token_uri="https://oauth2.googleapis.com/token",
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def google_drive_account_email(client_id: str, client_secret: str, refresh_token: str) -> str | None:
    try:
        service = _drive_service(client_id, client_secret, refresh_token)
        about = service.about().get(fields="user").execute()
        return about.get("user", {}).get("emailAddress")
    except Exception:
        log.exception("Echec lecture compte Google Drive")
        return None


def _drive_folder_id(service) -> str:
    q = f"name = '{BACKUP_FOLDER_NAME}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    result = service.files().list(q=q, fields="files(id)").execute()
    files = result.get("files", [])
    if files:
        return files[0]["id"]
    folder = service.files().create(body={
        "name": BACKUP_FOLDER_NAME,
        "mimeType": "application/vnd.google-apps.folder",
    }, fields="id").execute()
    return folder["id"]


def google_drive_upload(client_id: str, client_secret: str, refresh_token: str, local_path: Path, remote_filename: str, bandwidth_limit_kbps: int | None = None) -> str:
    from googleapiclient.http import MediaFileUpload

    service = _drive_service(client_id, client_secret, refresh_token)
    folder_id = _drive_folder_id(service)

    # Supprime une eventuelle version precedente du meme nom (equivalent "overwrite")
    q = f"name = '{remote_filename}' and '{folder_id}' in parents and trashed = false"
    existing = service.files().list(q=q, fields="files(id)").execute().get("files", [])
    for f in existing:
        service.files().delete(fileId=f["id"]).execute()

    media = MediaFileUpload(str(local_path), chunksize=_CHUNK_SIZE, resumable=True)
    request = service.files().create(
        body={"name": remote_filename, "parents": [folder_id]},
        media_body=media, fields="id",
    )
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            _sleep_for_chunk(status.resumable_progress, bandwidth_limit_kbps)
    return response["id"]


def google_drive_list_backups(client_id: str, client_secret: str, refresh_token: str) -> list[dict]:
    service = _drive_service(client_id, client_secret, refresh_token)
    folder_id = _drive_folder_id(service)
    result = service.files().list(
        q=f"'{folder_id}' in parents and trashed = false",
        fields="files(id, name, createdTime)",
    ).execute()
    return result.get("files", [])


def google_drive_delete(client_id: str, client_secret: str, refresh_token: str, file_id: str):
    service = _drive_service(client_id, client_secret, refresh_token)
    service.files().delete(fileId=file_id).execute()
