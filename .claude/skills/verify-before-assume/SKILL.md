---
name: verify-before-assume
description: Methode obligatoire avant toute affirmation technique sur SIPV ou ERPCRM -- identifier la source de verite reelle et prouver plutot que supposer. A utiliser des qu'une question porte sur "comment ca marche", "est-ce que X existe deja", ou avant de conclure une investigation.
---

# Verifier avant de supposer

Regle fondatrice du projet Simple IP Platform : ne jamais remplir un trou par une conclusion vraisemblable.

## Methode

1. **Identifier le type de question** et la source de verite qui y repond (voir table plus bas).
2. **Chercher dans le code reel** via Serena (`serena-sipv` et/ou `serena-erpcrm`) -- `find_symbol`, `get_symbols_overview`, `find_referencing_symbols`. Ne pas deviner un chemin de fichier : le chercher.
3. **Verifier la DB** si la question porte sur des donnees (requete reelle, pas une supposition sur le schema).
4. **Verifier le runtime reel**, pas seulement la config sur disque : `fs_cli`, `kamctl`/logs Kamailio, `systemctl status`, `journalctl`. Un fichier de config modifie n'est pas applique tant qu'un reload/restart n'a pas ete fait.
5. **Utiliser Git** pour l'historique plutot que de deviner pourquoi quelque chose existe.
6. **Utiliser Graphiti** (`graphiti-platform`, cote ERPCRM, accessible via le workflow transversal) pour le contexte/decisions passees.
7. **Comparer les sources.** En cas de contradiction, le runtime gagne pour l'etat actuel.
8. **Produire un niveau de confiance explicite** dans la reponse finale.

## Source de verite par type de question

| Question | Source prioritaire |
|---|---|
| Que fait le code aujourd'hui ? | Serena + lecture du code |
| Quel est le comportement actuel ? | Runtime reel (fs_cli, kamctl, logs) -- jamais juste le fichier sur disque |
| Pourquoi ca a ete construit ainsi ? | BUILD_HISTORY.md + Graphiti |
| Quelles erreurs deja rencontrees ? | ERRORS_LESSONS.md + Graphiti |
| Qu'est-ce qu'il reste a faire ? | PLATFORM_TASKS.md |

## Vocabulaire de conclusion obligatoire

PROUVE / TRES PROBABLE / HYPOTHESE / REFUTE / A VERIFIER -- jamais une affirmation nue pour une investigation non triviale.

## Ne jamais faire

- Affirmer qu'un module FreeSWITCH/route Kamailio est charge sans l'avoir verifie en direct (`fs_cli -x 'module_exists ...'`, pas juste "c'est dans la config").
- Traiter TASKSIPV.md comme forcement a jour -- guide, pas verite absolue.
- Confondre config sur disque et config reellement chargee.
