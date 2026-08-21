---
name: freeswitch-investigation
description: Methode pour investiguer un comportement ou ajouter une fonctionnalite FreeSWITCH (dialplan, modules, applications). A utiliser pour tout travail touchant le dialplan, les applications mod_*, ou le routage d'appel.
---

# Investigation FreeSWITCH

## Ne jamais supposer le comportement d'une application/module

Toujours verifier dans le vrai source charge sur le serveur avant de coder contre une application FreeSWITCH :

1. `fs_cli -x 'module_exists <mod>'` -- le module est-il vraiment charge ?
2. `fs_cli -x 'show application/api'` -- l'application existe-t-elle vraiment, avec cette syntaxe exacte ?
3. Lire le source C reel si present sur le serveur (`/usr/src/freeswitch-*/src/mod/...`) plutot que de supposer le comportement depuis la documentation en ligne, qui peut etre datee.
4. Verifier les variables natives disponibles (ex: `valet_parking_timeout`, `valet_parking_orbit_exten` pour le parcage) avant d'inventer une logique maison.

## Erreurs deja rencontrees a ne pas refaire

- `valet_park_fetch` n'existe pas -- l'application `valet_park` gere park ET reprise selon l'etat de l'appel (comportement toggle natif).
- Un module non charge par defaut (ex: `mod_say_fr`) peut avoir son source deja present sans etre compile/charge -- verifier `module_exists` avant de conclure qu'une fonctionnalite est absente du systeme.
- L'emission d'un evenement (ex: `SWITCH_EVENT_PRESENCE_IN`) ne garantit pas l'affichage cote telephone -- toujours tester sur un vrai poste avant de declarer une fonctionnalite BLF terminee.

## Avant de modifier le dialplan

- Valider le XML programmatiquement avant tout `reloadxml` (piege `--` dans les commentaires, voir `sipv-runtime-verification`).
- Preferer une regle avec alternation regex a la duplication d'extensions similaires.
- Tester sur un poste reel quand la fonctionnalite le permet (BLF, MOH, annonces) -- le comportement API/log ne suffit pas a prouver le comportement utilisateur.
