"""
Suivi de reprise de position MOH par appel (TASK-S058.3 + TASK-S061 item 6).

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

── Extension parcage (TASK-S061 item 6, 2026-08-20) ──────────────────────
mod_valet_parking ne déclenche JAMAIS CHANNEL_HOLD/CHANNEL_UNHOLD -- il a
son propre événement custom `valet_parking::info` (Action=hold au début du
parcage, Action=exit à la fin -- reprise, timeout, ou raccroché, confondus).
Chaque park relance donc sa propre lecture MOH depuis zéro, meme mécanisme
de fond que le Hold classique mais jamais couvert par le code ci-dessus.

Différence structurelle importante par rapport au Hold classique : pour un
parcage, c'est le MÊME UUID de canal qui joue sa propre MOH à chaque cycle
(confirmé le 2026-08-19 : variable_call_uuid reste identique à travers
park -> reprise -> re-park -> reprise, seul le UUID du RETRIEVER change à
chaque fois). Pas de notion de "partenaire" ici -- on lit
playback_last_offset_pos sur SOI-MÊME, pas sur un autre canal.

Séquençage : `music` (le fichier a jouer) est résolu par mod_valet_parking
AVANT que l'événement Action=hold ne soit émis (confirmé dans
mod_valet_parking.c) -- réagir à Action=hold pour régler la variable serait
donc toujours en retard d'un cycle. La bonne séquence : réagir à
Action=exit (fin du cycle courant) pour calculer l'offset et préparer
valet_hold_music AVANT le prochain park éventuel de ce même appel -- exact
miroir de _handle_unhold ci-dessus, sans partenaire.
"""
import asyncio
import logging
from urllib.parse import unquote

from app.core.config import settings
from app.core.esl import get_esl

logger = logging.getLogger(__name__)

_HOLD_EVENTS = ("CHANNEL_HOLD", "CHANNEL_UNHOLD", "CHANNEL_HANGUP_COMPLETE")
_VALET_SUBCLASS = "valet_parking::info"

# uuid (poste qui a fait Hold) -> {"partner": uuid, "base": "/chemin/fichier.wav"}
_state: dict[str, dict] = {}

# uuid (appel parke) -> {"base": "/chemin/fichier.wav"} -- pas de partenaire,
# c'est le meme canal qui joue sa propre MOH a chaque cycle de parcage.
_valet_state: dict[str, dict] = {}

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
    """
    Format "event plain" de FreeSWITCH : les valeurs sont URL-encodees
    (confirme en direct le 2026-08-20 -- Event-Subclass arrive sous la forme
    "valet_parking%3A%3Ainfo", pas "valet_parking::info"). Sans unquote() ici,
    aucune comparaison exacte de valeur (Event-Subclass, Action, etc.) ne peut
    jamais matcher -- c'etait la cause reelle du "CUSTOM valet_parking::info
    jamais recu", pas un probleme d'abonnement ESL.
    """
    headers = {}
    for line in body.split("\n"):
        if ": " in line:
            k, v = line.split(": ", 1)
            headers[k.strip()] = unquote(v.strip())
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


async def _handle_valet_hold(ev: dict):
    """Capture le fichier de base la premiere fois qu'on voit cet appel parque."""
    uuid = ev.get("Unique-ID")
    logger.warning("DEBUG-VALET-HOLD entree uuid=%r deja_connu=%s", uuid, uuid in _valet_state if uuid else None)
    if not uuid or uuid in _valet_state:
        return
    esl = await get_esl()
    current = await esl.uuid_getvar(uuid, "valet_hold_music")
    logger.warning("DEBUG-VALET-HOLD valet_hold_music brut=%r", current)
    # uuid_getvar renvoie litteralement la chaine "_undef_" pour une variable
    # non definie (ni vide, ni prefixee "-ERR") -- confirme en direct le
    # 2026-08-20, c'etait la vraie cause du fallback jamais declenche.
    if not current or current.strip() in ("_undef_", "") or current.strip().startswith("-ERR"):
        current = await esl.uuid_getvar(uuid, "hold_music")
        logger.warning("DEBUG-VALET-HOLD fallback hold_music brut=%r", current)
    base = _extract_base_path(current)
    logger.warning("DEBUG-VALET-HOLD base extraite=%r", base)
    if not base:
        return
    _valet_state[uuid] = {"base": base}
    logger.warning("DEBUG-VALET-HOLD etat memorise pour uuid=%s base=%s", uuid, base)


async def _handle_valet_exit(ev: dict):
    """
    Fin d'un cycle de parcage (reprise, timeout, ou raccroche -- Action=exit
    ne distingue pas, mais lire l'offset et le preparer pour le prochain
    park ne fait de mal dans aucun de ces 3 cas) -- calcule et memorise
    l'offset pour que le PROCHAIN park de ce meme appel reprenne dessus.
    """
    uuid = ev.get("Unique-ID")
    st = _valet_state.get(uuid) if uuid else None
    logger.warning("DEBUG-VALET-EXIT entree uuid=%r etat_connu=%s", uuid, st)
    if not st:
        return

    esl = await get_esl()
    offset_raw = (await esl.uuid_getvar(uuid, "playback_last_offset_pos")).strip()
    logger.warning("DEBUG-VALET-EXIT playback_last_offset_pos brut=%r", offset_raw)
    if not offset_raw.isdigit():
        return
    offset = int(offset_raw)
    if offset <= 0:
        return

    new_valet_hold_music = f"playback::{st['base']}@@{offset}"
    await esl.api(f"uuid_setvar {uuid} valet_hold_music {new_valet_hold_music}")
    logger.warning("MOH resume (parcage): %s -> offset=%d", uuid, offset)


def _cleanup(uuid: str | None):
    if uuid:
        _state.pop(uuid, None)
        _valet_state.pop(uuid, None)


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

                # Deux commandes separees : un abonnement CUSTOM+subclass ne peut pas
                # se melanger avec des noms d'evenements standard dans la meme
                # commande ESL (bug trouve et corrige le 2026-08-19 dans le moniteur
                # de diagnostic de cette session -- meme piege ici, evite d'emblee).
                writer.write(f"event plain {' '.join(_HOLD_EVENTS)}\n\n".encode())
                await writer.drain()
                await _read_packet(reader)  # subscribe reply

                writer.write(f"event plain CUSTOM {_VALET_SUBCLASS}\n\n".encode())
                await writer.drain()
                await _read_packet(reader)  # subscribe reply

                logger.info("MOH hold tracker: connecté et abonné (%s + CUSTOM %s)", ", ".join(_HOLD_EVENTS), _VALET_SUBCLASS)
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
                    elif name == "CUSTOM" and ev.get("Event-Subclass") == _VALET_SUBCLASS:
                        action = ev.get("Action")
                        if action == "hold":
                            await _handle_valet_hold(ev)
                        elif action == "exit":
                            await _handle_valet_exit(ev)
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
    _valet_state.clear()
