---
name: documentation-sync
description: Maintenir PLATFORM_TASKS/BUILD_HISTORY/ERRORS_LESSONS a jour apres une fonctionnalite ou une erreur importante cote SIPV. A utiliser a la fin de tout travail non-trivial.
---

# Synchronisation documentaire (cote SIPV)

Simple IP Platform a une gestion de projet canonique commune (voir ARCHITECTURE_PLATFORM.md dans le depot ERPCRM, qui heberge la documentation plateforme). SIPV garde localement sa documentation technique specifique (installation, FreeSWITCH, Kamailio, RTPengine, runtime, depannage) -- CLAUDE.md et docs locales restent d'actualite pour ca.

## Apres une fonctionnalite ou un fix cote SIPV

1. Mettre a jour `TASKSIPV.md` (ou `PLATFORM_TASKS.md` une fois la migration faite) avec le statut reel.
2. Toute erreur significative (a coute du temps, revele une particularite FreeSWITCH/Kamailio/RTPengine, contredit une doc existante) va dans `ERRORS_LESSONS.md`.
3. Une decision d'architecture structurante va dans `ARCHITECTURE_PLATFORM.md` -- ne pas la laisser seulement dans un commentaire de code ou une entree TASKSIPV.md.

## Ne jamais faire

- Documenter une hypothese comme un fait etabli sans l'avoir testee en reel (voir `sipv-runtime-verification`).
- Laisser une note "a confirmer avec Philippe" sans suite -- soit la tester, soit la garder explicitement comme point ouvert dans TASKSIPV.md.
