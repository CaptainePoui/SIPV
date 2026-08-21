---
name: debug-with-agent-team
description: Quand et comment utiliser plusieurs agents independants pour un probleme SIPV complexe (SIP/FreeSWITCH/Kamailio/RTPengine difficile, hypotheses concurrentes). A utiliser pour les problemes couteux a se tromper.
---

# Debug avec plusieurs agents (cote SIPV)

## Limitation connue (verifiee reellement le 2026-08-21)

La messagerie directe teammate-a-teammate par nom ("Agent Teams" documente par Claude Code) ne fonctionne pas dans cet environnement -- testee et confirmee cassee. Le pattern qui fonctionne reellement est le **lead-mediateur** : plusieurs agents independants qui rapportent chacun au lead, qui compare et synthetise -- pas une vraie coordination autonome entre agents.

## Quand favoriser plusieurs agents

- Probleme SIP/FreeSWITCH/Kamailio/RTPengine/NAT/media difficile a diagnostiquer seul
- Hypotheses concurrentes sur la cause d'un bug telephonique
- Contradiction entre deux sources (doc vs runtime, par exemple)

## Methode

1. Question factuelle precise et verifiable.
2. Agents independants avec instructions explicitement adversariales (confirmer vs refuter).
3. Un agent "skeptic" qui ne cherche que les preuves manquantes.
4. Attendre les vraies notifications, ne jamais fabriquer un resultat.
5. Synthese par le lead avec le vocabulaire PROUVE/TRES PROBABLE/HYPOTHESE/REFUTE.
