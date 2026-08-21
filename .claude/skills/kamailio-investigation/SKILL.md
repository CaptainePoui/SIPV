---
name: kamailio-investigation
description: Methode pour investiguer le routage SIP/Kamailio. A utiliser pour tout travail touchant les routes, le registrar, ou l'interconnexion avec FreeSWITCH/RTPengine.
---

# Investigation Kamailio

## Verifier avant de supposer

- Les routes reellement chargees, pas juste le fichier de config source.
- La version de Kamailio installee et les modules charges (`kamctl` ou equivalent).
- Le flux reel d'un appel (Kamailio -> FreeSWITCH -> RTPengine) via les logs, pas une hypothese d'architecture.

## Points de vigilance connus

- Transport SIP : deja cable et verifie en production (voir historique -- ne pas repartir de zero sur ce point sans verifier l'etat actuel d'abord).
- Toute modification de route doit etre testee avec un appel/registration reel avant d'etre consideree terminee -- pas seulement une relecture de la config.

## Lien avec le reste de la plateforme

Kamailio fait partie du Telephony Plane (autonomie runtime -- voir `sipv-runtime-verification`). Un changement ici ne doit jamais dependre d'ERPCRM/Serena/Graphiti pour fonctionner en production.
