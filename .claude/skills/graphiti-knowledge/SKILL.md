---
name: graphiti-knowledge
description: Comment interroger Graphiti (memoire relationnelle de la plateforme) depuis une session SIPV. A utiliser pour TOUTE demande, pas seulement "pourquoi/historique/erreurs deja rencontrees".
---

# Utiliser Graphiti depuis SIPV

Graphiti tourne sur la VM ERPCRM (`tools/knowledge/graphiti/`), pas sur SIPV -- SIPV n'a pas besoin d'heberger sa propre instance, la connaissance de toute la plateforme (ERPCRM + SIPV) y est centralisee.

## Etat actuel (verifier avant d'utiliser)

Le service `graphiti-mcp` cote ERPCRM ne demarre qu'avec `OPENAI_API_KEY` configuree -- verifier son etat reel plutot que de supposer qu'il repond.

## Quand interroger Graphiti (revise 2026-09-10, EN PREMIER sur toute demande sans exception)

**Correction explicite de Philippe (cote ERPCRM, 2026-09-10) applicable ici aussi** : pas de tri par jugement entre demandes "importantes" et "mecaniques" -- interroger Graphiti sur TOUTE demande touchant le projet, sans exception, avant d'agir.

Cas d'usage typiques (liste illustrative, pas limitative) :
- Nouvelle fonctionnalite, bug, decision d'approche sur SIPV -- chercher le(s) module(s) concerne(s) AVANT de coder.
- "Pourquoi cette architecture SIPV a ete choisie ?", "quelles erreurs deja rencontrees sur le parcage/FreeSWITCH/Kamailio ?", "cette decision a-t-elle deja ete remplacee ?"
- Toute autre demande, meme une correction mineure ou une question courte.

Pas pour "que fait le code aujourd'hui" (Serena) ni "qu'est-ce qu'il reste a faire" (PLATFORM_TASKS.md, section SIPV -- vit sur le depot ERPCRM, un seul fichier pour toute la plateforme).

## Quand alimenter Graphiti -- ECRITURE CONSTRUITE (2026-09-10, TASK-S062)

SIPV ecrit maintenant dans Graphiti via une file locale, pas directement dans le conteneur (qui vit sur ERPCRM) :
1. `python3 scripts/graphiti_queue_fact.py <<< '{"type": "triplet", "source": "NomExact", "edge_name": "RELATES_TO", "fact": "...(le pourquoi, reference TASK-SXXX)...", "target": "NomExact"}'` -- ajoute a `scripts/graphiti_queue.jsonl` (local, jamais commite).
2. Cron `scripts/push_graphiti_queue.py` (a la minute) pousse ce fichier par scp vers `erpcrm:/home/simpleip/erpcrm/tools/knowledge/graphiti/incoming/sipv.jsonl` (alias SSH `erpcrm`, cle dediee `id_ed25519_erpcrm` -- non restreinte, voir memoire persistante pour le choix).
3. Le consommateur de file cote ERPCRM (`graphiti_queue_consumer.py`) traite la nouvelle ligne via `add_triplet` (graphiti-core, PAS le chemin rapide `fast_write.py`) -- **LENT** : ~7-8 min par fait sur ce materiel CPU-seul (meme limite que TASK-040.9), parce que ce chemin fait une resolution/dedup par LLM. Teste et confirme fonctionnel de bout en bout le 2026-09-10.

Meme discipline que cote ERPCRM avant d'ecrire : verifier que le concept/la relation n'existe pas deja (demander a Claude cote ERPCRM ou chercher dans une session qui a acces a Graphiti) -- ce script n'a aucune verification integree, il fait confiance a l'appelant.

## Hierarchie en cas de contradiction

Le runtime SIPV reel gagne toujours sur ce que Graphiti pourrait indiquer pour une question d'etat actuel -- Graphiti garde l'historique, pas la verite courante.
