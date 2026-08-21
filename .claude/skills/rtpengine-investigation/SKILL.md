---
name: rtpengine-investigation
description: Methode pour investiguer le proxy media RTPengine. A utiliser pour tout travail touchant le media/RTP, le NAT, ou les enregistrements d'appel.
---

# Investigation RTPengine

## Verifier avant de supposer

- Statut reel du daemon (`rtpengine-daemon.service`, `rtpengine-recording-daemon.service`) et des sessions actives, pas juste "le service est demarre".
- Le comportement media reel (NAT traversal, transferts) doit etre teste sur un appel reel quand possible -- les problemes RTP/NAT sont notoirement difficiles a diagnostiquer sans test direct.

## Lien avec le reste de la plateforme

RTPengine fait partie du Telephony Plane (autonomie runtime). Pour un probleme media/NAT difficile a diagnostiquer, envisager `debug-with-agent-team` (hypotheses concurrentes) plutot que de s'enfoncer seul dans une seule piste.
