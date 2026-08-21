---
name: graphiti-knowledge
description: Comment interroger Graphiti (memoire relationnelle de la plateforme) depuis une session SIPV. A utiliser pour une question "pourquoi/historique/erreurs deja rencontrees".
---

# Utiliser Graphiti depuis SIPV

Graphiti tourne sur la VM ERPCRM (`tools/knowledge/graphiti/`), pas sur SIPV -- SIPV n'a pas besoin d'heberger sa propre instance, la connaissance de toute la plateforme (ERPCRM + SIPV) y est centralisee.

## Etat actuel (verifier avant d'utiliser)

Le service `graphiti-mcp` cote ERPCRM ne demarre qu'avec `OPENAI_API_KEY` configuree -- verifier son etat reel plutot que de supposer qu'il repond.

## Quand l'utiliser

"Pourquoi cette architecture SIPV a ete choisie", "quelles erreurs deja rencontrees sur le parcage/FreeSWITCH/Kamailio", "cette decision a-t-elle deja ete remplacee". Pas pour "que fait le code aujourd'hui" (Serena) ni "qu'est-ce qu'il reste a faire" (PLATFORM_TASKS.md).

## Hierarchie en cas de contradiction

Le runtime SIPV reel gagne toujours sur ce que Graphiti pourrait indiquer pour une question d'etat actuel -- Graphiti garde l'historique, pas la verite courante.
