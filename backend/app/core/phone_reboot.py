"""Redemarrer les telephones d'un poste a distance (bouton « Redemarrer » d'ERPCRM, TASK-051, 2026-10-10).

Le telephone exige que l'ordre (NOTIFY check-sync) soit authentifie avec les identifiants SIP du compte ; FreeSWITCH ne
sait pas repondre a ce defi. On demande donc a Kamailio (par qui passent les telephones) d'envoyer le NOTIFY et de
repondre au defi (module uac) -- demande interne protegee par KAMAILIO_CTRL_KEY. Le contact et le domaine viennent des
enregistrements reels (jamais reconstruits par convention, voir ERRORS_LESSONS TASK-051). Si Kamailio ne repond pas,
repli sur le check_sync de FreeSWITCH (sans authentification, n'efface pas l'enregistrement)."""
import asyncio
import re
import secrets
import socket

from app.core.esl import get_esl

KAMAILIO = ("192.168.1.55", 5060)


def _ctrl_key() -> str:
    from app.core.config import settings
    return settings.KAMAILIO_CTRL_KEY


async def registrations(username: str) -> list[dict]:
    """[{realm, contact}] des enregistrements reels du poste."""
    esl = await get_esl()
    text = await esl.api("sofia status profile internal reg")
    out, cur = [], None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("Call-ID:"):
            cur = {}
        elif s.startswith("User:") and cur is not None:
            who = s.split()[-1]
            cur["user"], _, cur["realm"] = who.partition("@")
        elif s.startswith("Contact:") and cur is not None:
            m = re.search(r"<([^>]+)>", s)
            if m:
                cur["contact"] = re.sub(r";fs_path=[^;>]*", "", m.group(1))
            if cur.get("user") == username and cur.get("contact"):
                out.append({"realm": cur["realm"], "contact": cur["contact"]})
    return out


async def registered_users() -> set[str]:
    """Identifiants SIP enregistres en ce moment (une seule lecture, pour une liste de postes)."""
    esl = await get_esl()
    text = await esl.api("sofia status profile internal reg")
    return {l.strip().split()[-1].partition("@")[0] for l in text.splitlines() if l.strip().startswith("User:")}


async def registered_realms(username: str) -> set[str]:
    return {r["realm"] for r in await registrations(username)}


def _send_to_kamailio(contact: str, identity: str, user: str, password: str, key: str, event: str = "check-sync") -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)
    try:
        sock.bind((KAMAILIO[0], 0))
        port = sock.getsockname()[1]
        branch, tag, callid = secrets.token_hex(8), secrets.token_hex(4), secrets.token_hex(12)
        msg = (f"MESSAGE sip:sipv-check-sync@{KAMAILIO[0]} SIP/2.0\r\n"
               f"Via: SIP/2.0/UDP {KAMAILIO[0]}:{port};branch=z9hG4bK{branch};rport\r\n"
               f"Max-Forwards: 70\r\nFrom: <sip:sipv@{KAMAILIO[0]}>;tag={tag}\r\nTo: <sip:sipv-check-sync@{KAMAILIO[0]}>\r\n"
               f"Call-ID: {callid}\r\nCSeq: 1 MESSAGE\r\nX-Sipv-Key: {key}\r\nX-Target: {contact}\r\nX-Identity: {identity}\r\n"
               f"X-Auth-User: {user}\r\nX-Auth-Pass: {password}\r\nX-Event: {event}\r\nContent-Length: 0\r\n\r\n")
        sock.sendto(msg.encode(), KAMAILIO)
        data, _ = sock.recvfrom(4096)
        return data.startswith(b"SIP/2.0 202")
    except OSError:
        return False
    finally:
        sock.close()


async def reboot_phones(username: str, password: str | None = None, reboot: bool = True) -> int:
    """Nombre d'enregistrements a qui l'ordre a ete envoye (0 = aucun telephone enregistre). reboot=False : « Pousser la
    config » (Philippe, 2026-10-14) -- le telephone relit sa configuration sans redemarrer (check-sync;reboot=false)."""
    regs = await registrations(username)
    key = _ctrl_key()
    event = "check-sync" if reboot else "check-sync;reboot=false"
    esl = None
    for r in regs:
        ok = False
        if password and key:
            ok = await asyncio.to_thread(_send_to_kamailio, r["contact"], f"sip:{username}@{r['realm']}", username, password, key, event)
        if not ok and reboot:   # repli : FreeSWITCH (sans authentification ; refuse par un telephone qui l'exige)
            esl = esl or await get_esl()
            await esl.api(f"sofia profile internal check_sync {username}@{r['realm']}")
        elif not ok:
            raise RuntimeError("Kamailio n'a pas accepté l'ordre")
    return len(regs)
