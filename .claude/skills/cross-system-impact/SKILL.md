---
name: cross-system-impact
description: Verifier qu'un changement SIPV qui a une contrepartie ERPCRM est bien coordonne avec elle. A utiliser avant tout changement de modele/API SIPV qui a un equivalent visible cote ERPCRM.
---

# Impact cross-systeme (cote SIPV)

SIPV est le Telephony Plane, source de verite pour tout ce qui est validation telephonique (numerotation, collisions, capacites). ERPCRM proxie cette logique, ne la duplique pas -- donc un changement de validation cote SIPV doit rester coherent avec ce que ERPCRM attend.

## Avant de changer un modele/endpoint expose a ERPCRM

1. Verifier `sipv_client.py` cote ERPCRM (si accessible) pour voir comment le champ/endpoint est consomme.
2. Ne pas casser silencieusement un contrat d'API que ERPCRM utilise deja.
3. Documenter le changement des deux cotes si le comportement change (voir `documentation-sync`).

## Une tache SHARED n'est pas deux taches separees

Exemple Parking Lot (TASK-S061 cote SIPV / TASK-038 cote ERPCRM) : documenter le lien explicite entre les deux cote de chaque fichier TASK, plutot que de les traiter comme independants.

## Ne jamais faire

- Changer un format de reponse API consomme par ERPCRM sans verifier l'impact.
- Dupliquer cote SIPV une logique qui devrait rester dans ERPCRM (Control Plane).
