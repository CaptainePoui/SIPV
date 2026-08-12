"""
Suivi de reprise de position MOH par appel (TASK-S058.3).

FreeSWITCH ne mémorise pas où une musique d'attente s'était arrêtée entre
deux Hold d'un même appel -- chaque Hold relance hold_music depuis le
début (vérifié dans switch_core_media.c : switch_ivr_broadcast() est
rappelé à chaque bascule, sans aucun état conservé). Ce module écoute les
événements CHANNEL_HOLD / CHANNEL_UNHOLD via une connexion ESL dédiée
(event stream en lecture seule), et entre deux Hold du même appel,
réécrit hold_music sur le poste qui a mis en attente avec un offset
(`playback::<fichier>@@<sample>`) lu sur playback_last_offset_pos du
partenaire (celui dont le canal joue réellement la MOH -- confirmé par
switch_ivr_play_say.c, posé inconditionnellement à l'arrêt de la lecture,
normal ou interrompue).

Mécanisme prouvé manuellement en direct le 2026-08-12 (postes 102/103)
avant d'écrire ce service, avec uuid_setvar/uuid_getvar bruts.

Un nouvel appel = nouveaux UUID = aucune entrée dans _state = repart à
zéro (cohérent avec TASK-S058.4, qui a déjà retiré local_stream:// pour
cette raison).

Limite connue et acceptée : si un cycle de Hold dépasse la durée du
fichier MOH en cours dans une liste de plusieurs pistes (mode Liste),
la reprise suivante cible ce même fichier avec l'offset lu -- pas de
suivi précis multi-fichiers pour l'instant (nécessiterait de savoir
quel fichier de la chaîne file_string était ouvert à l'arrêt, ce que
FreeSWITCH n'expose pas). En mode Aléatoire (un seul fichier par appel),
ce cas ne se produit pas. En cas de valeur incohérente, l'échec est
silencieux -- l'appel retombe simplement sur le comportement par défaut
(recommence au début), jamais une lecture corrompue.
"""
import asyncio
import logging

from app.core.config import settings
from app.core.esl import get_esl

logger = logging.getLogger(__name__)

_HOLD_EVENTS = ("CHANNEL_HOLD", "CHANNEL_UNHOLD", "CHANNEL_HANGUP_COMPLETE")

# uuid (poste qui a fait Hold) -> {"partner": uuid, "base": "/chemin/fichier.wav"}
_state: dict[str, dict] = {}

_task: "asyncio.Task | None" = None
_stop = False


def _extract_base_path(hold_music_value: str) -> str | None:
    """
    Extrait le premier vrai chemin .wav depuis une valeur hold_music
    (file_string://silence_stream://500!f1!f2... ou playback::f.wav ou
    playback::f.wav@@N). Retourne None si rien d'utilisable (ex: -ERR).
    """
    v = (hold_music_value or "").strip()
    if v.startswith("playback::"):
        v = v[len("playback::"):]
        return v.split("@@")[0] or None
    if v.startswith("file_string://"):
        v = v[len("file_string://"):]
        for part in v.split("!"):
            if part and not part.startswith("silence_stream://"):
                return part
    return None


async def _read_packet(reader: asyncio.StreamReader) -> tuple[dict, str]:
    raw = await reader.readuntil(b"\n\n")
    headers: dict[str, str] = {}
    for line in raw.decode(errors="replace").strip().split("\n"):
        if ": " in line:
            k, v = line.split(": ", 1)
            headers[k.strip()] = v.strip()
    body = ""
    if "Content-Length" in headers:
        n = int(headers["Content-Length"])
        body_bytes = await reader.readexactly(n)
        body = body_bytes.decode("utf-8", errors="replace")
    else:
        body = headers.get("Reply-Text", "")
    return headers, body


def _parse_event_body(body: str) -> dict:
    headers = {}
    for line in body.split("\n"):
        if ": " in line:
            k, v = line.split(": ", 1)
            headers[k.strip()] = v.strip()
    return headers


async def _handle_hold(ev: dict):
    holder = ev.get("Unique-ID")
    partner = ev.get("Other-Leg-Unique-ID")
    if not holder or not partner:
        return
    if holder not in _state:
        esl = await get_esl()
        current = await esl.uuid_getvar(holder, "hold_music")
        base = _extract_base_path(current)
        if not base:
            return
        _state[holder] = {"partner": partner, "base": base}
    else:
        _state[holder]["partner"] = partner


async def _handle_unhold(ev: dict):
    holder = ev.get("Unique-ID")
    st = _state.get(holder) if holder else None
    if not st:
        return
    partner = ev.get("Other-Leg-Unique-ID") or st.get("partner")
    if not partner:
        return

    esl = await get_esl()
    offset_raw = (await esl.uuid_getvar(partner, "playback_last_offset_pos")).strip()
    if not offset_raw.isdigit():
        return
    offset = int(offset_raw)
    if offset <= 0:
        return

    new_hold_music = f"playback::{st['base']}@@{offset}"
    await esl.api(f"uuid_setvar {holder} hold_music {new_hold_music}")
    logger.info("MOH resume: %s -> offset=%d (partner=%s)", holder, offset, partner)


def _cleanup(uuid: str | None):
    if uuid:
        _state.pop(uuid, None)


async def _run():
    global _stop
    backoff = 1
    while not _stop:
        try:
            reader, writer = await asyncio.open_connection(settings.FREESWITCH_HOST, settings.FREESWITCH_ESL_PORT)
            try:
                await _read_packet(reader)  # auth request
                writer.write(f"auth {settings.FREESWITCH_ESL_PASSWORD}\n\n".encode())
                await writer.drain()
                _, body = await _read_packet(reader)
                if "+OK" not in body:
                    raise RuntimeError(f"ESL auth refusée: {body}")

                writer.write(f"event plain {' '.join(_HOLD_EVENTS)}\n\n".encode())
                await writer.drain()
                await _read_packet(reader)  # subscribe reply

                logger.info("MOH hold tracker: connecté et abonné (%s)", ", ".join(_HOLD_EVENTS))
                backoff = 1

                while not _stop:
                    headers, body = await _read_packet(reader)
                    if headers.get("Content-Type") != "text/event-plain":
                        continue
                    ev = _parse_event_body(body)
                    name = ev.get("Event-Name")
                    if name == "CHANNEL_HOLD":
                        await _handle_hold(ev)
                    elif name == "CHANNEL_UNHOLD":
                        await _handle_unhold(ev)
                    elif name == "CHANNEL_HANGUP_COMPLETE":
                        _cleanup(ev.get("Unique-ID"))
                        _cleanup(ev.get("Other-Leg-Unique-ID"))
            finally:
                writer.close()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("MOH hold tracker: connexion perdue (%s), reconnexion dans %ds", exc, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)


async def hold_tracker_startup():
    global _task, _stop
    _stop = False
    _task = asyncio.create_task(_run())


async def hold_tracker_shutdown():
    global _task, _stop
    _stop = True
    if _task:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
    _state.clear()
