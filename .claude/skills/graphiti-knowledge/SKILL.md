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

## Quand alimenter Graphiti -- ECRITURE PAS ENCORE CONSTRUITE DEPUIS SIPV (2026-09-10)

Contrairement a ERPCRM (qui ecrit directement via `fast_write.py` dans le conteneur), **SIPV n'a aujourd'hui aucun mecanisme pour ecrire de nouveaux faits dans Graphiti** -- ni script, ni cron. Le mecanisme prevu (voir `tools/knowledge/graphiti/scripts/graphiti_queue_consumer.py` cote ERPCRM, section "incoming/*.jsonl -- pousses par SIPV/DashV16 via scp depuis leur propre cron") n'a jamais ete construit cote SIPV. Backlog ouvert -- voir PLATFORM_TASKS.md (section SIPV) pour le numero de tache une fois cree. Ne PAS improviser une ecriture directe vers le conteneur ERPCRM depuis une session SIPV (violerait l'autonomie SIPV -- voir memoire persistante `feedback_sipv_must_stay_autonomous`) : tant que ce mecanisme n'existe pas, signaler a Philippe qu'un fait merite d'etre ajoute plutot que d'ecrire directement.

## Hierarchie en cas de contradiction

Le runtime SIPV reel gagne toujours sur ce que Graphiti pourrait indiquer pour une question d'etat actuel -- Graphiti garde l'historique, pas la verite courante.
