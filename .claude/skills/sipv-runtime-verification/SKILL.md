---
name: sipv-runtime-verification
description: Distinguer configuration sur disque et configuration reellement chargee sur SIPV. A utiliser avant d'affirmer qu'un comportement telephonique est actif, apres tout changement de dialplan/config, et pour tout diagnostic runtime.
---

# Verification runtime SIPV

Principe central : **SIPV doit rester autonome**. Le runtime telephonique (FreeSWITCH/Kamailio/RTPengine) continue de fonctionner meme si ERPCRM, Claude, Serena ou Graphiti sont indisponibles -- ne jamais construire de dependance runtime vers ces outils de developpement.

## Toujours distinguer

- **Configuration sur disque** (fichiers XML/config modifies)
- **Configuration reellement chargee** (ce que le process a en memoire)

Un fichier modifie n'affecte rien tant qu'un reload/restart n'a pas ete fait, et un restart peut lui-meme casser des appels en cours (voir regle de deploiement plus bas).

## Commandes de verification reelles

- FreeSWITCH : `fs_cli -x 'status'`, `fs_cli -x 'module_exists <mod>'`, `fs_cli -x 'show application/api'`, `fs_cli -x 'sofia status'`
- Kamailio : `kamctl` ou logs, verifier les routes chargees
- RTPengine : statut du daemon, sessions actives
- Services : `systemctl status freeswitch kamailio rtpengine-daemon sipv-backend sipv-backend-tls`

## Regle de deploiement (procedure apprise, incident 2026-08-20)

`sipv-backend` tourne sous `gunicorn` (plusieurs workers) precisement pour permettre un `systemctl reload` a chaud sans coupure de service. **Ne jamais faire `systemctl restart sipv-backend`** sauf process reellement mort -- un restart a deja fait tomber un poste en plein REGISTER/SUBSCRIBE. Toujours `reload` en premier reflexe.

## Piege XML connu (incident reel, deja survenu 2x)

Un commentaire XML contenant `--` casse le dialplan COMPLET du tenant (catch-all busy silencieux, pas d'erreur visible immediatement). Valider le XML genere programmatiquement apres tout changement de dialplan, avant tout `reloadxml`, pas seulement relire visuellement.

## Avant d'affirmer qu'une fonctionnalite marche

Ne jamais se fier a la presence du code ou du module charge seul -- confirmer sur un appel/test reel quand c'est possible (ex: annonce de parcage : module charge + macro presente, mais son jamais entendu -- reste "non fonctionnel" tant que non confirme).
