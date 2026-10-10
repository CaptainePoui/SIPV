"""Redemarrer les telephones d'un poste a distance (TASK-051 / bouton « Redemarrer » d'ERPCRM, 2026-10-10).

FreeSWITCH envoie un NOTIFY check-sync « reboot » a chaque enregistrement du poste : le telephone redemarre et relit sa
configuration (provisionnement). Le domaine d'enregistrement vient de l'appareil (ex. « sipv »), jamais du compte du
tenant : on le lit dans les enregistrements reels (voir ERRORS_LESSONS TASK-051)."""
from app.core.esl import get_esl


async def registered_realms(username: str) -> set[str]:
    esl = await get_esl()
    regs = await esl.api("sofia status profile internal reg")
    out = set()
    for line in regs.splitlines():
        parts = line.split()
        if line.strip().startswith("User:") and parts and "@" in parts[-1] and parts[-1].split("@")[0] == username:
            out.add(parts[-1].split("@", 1)[1])
    return out


async def reboot_phones(username: str) -> int:
    """Nombre d'enregistrements a qui l'ordre de redemarrer a ete envoye (0 = aucun telephone enregistre)."""
    esl = await get_esl()
    realms = await registered_realms(username)
    for realm in realms:
        # check_sync : envoie le NOTIFY sans toucher a l enregistrement. (flush_inbound_reg … reboot l effacait aussi :
        # si le telephone refusait l ordre, le serveur le croyait deconnecte jusqu a son prochain renouvellement.)
        await esl.api(f"sofia profile internal check_sync {username}@{realm}")
    return len(realms)
