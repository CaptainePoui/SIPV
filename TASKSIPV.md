# TASKS SIPV

## Politique de suivi — lire avant toute intervention

### Numérotation
- `TASK-SXXX` = création initiale d'un module SIPV
- `TASK-SXXX.Y` = ajout, fix ou extension sur ce module (Y = numéro séquentiel)
- **Chercher le numéro existant AVANT d'en créer un nouveau**

### Statuts
| Statut | Signification |
|--------|---------------|
| `[ ]`  | À faire |
| `[~]`  | Partiel — infrastructure en place mais câblage incomplet ou fonctionnalité incomplète |
| `[x]`  | Complété et validé |
| `[!]`  | Attention — bug connu, comportement inattendu, ou décision à revoir |

### Contenu obligatoire — tâche COMPLÉTÉE `[x]` ou PARTIELLE `[~]`
- **Fichiers touchés** : chemin complet de chaque fichier créé ou modifié
- **Migration Alembic** : numéro de révision + nom si applicable
- **Bugs rencontrés** : erreur exacte → correction appliquée (format ci-dessous)
- **Écarts vs plan** : si l'implémentation diffère du plan initial, noter quoi et pourquoi
- **Reste à faire** : si `[~]`, liste explicite de ce qui manque

```
⚠️ Bug : <description de l'erreur exacte>
   Fix  : <correction appliquée>
```

### Contenu obligatoire — tâche BACKLOG `[ ]`
- **Dépend de** : TASK-Sxxx qui doit être fait avant
- **Fichiers cibles** : où le travail aura lieu
- **Décisions prises** : choix d'architecture déjà arrêtés

### Règle de mise à jour
1. Mettre à jour **immédiatement après** l'implémentation, jamais avant
2. Si partiel → passer à `[~]` et lister explicitement ce qui manque
3. Ne jamais marquer `[x]` sans documenter les fichiers touchés
4. Bug découvert après `[x]` → créer TASK-Sxxx.Y (sous-tâche fix) et noter ici avec `[!]`
5. Mettre à jour le tableau récapitulatif du bloc en même temps que la description

## ⚠️ Points critiques à ne pas oublier
- Le code S001–S017 a été écrit pour **Asterisk PJSIP Realtime** (tables `ps_endpoints`, `ps_auths`, `ps_aors`, champ `asterisk_synced`).
- Le moteur retenu est **FreeSWITCH 1.10.12** via **mod_xml_curl** + **ESL** (greenswitch).
- La couche commit/sync (TASK-S017) doit être réécrite — voir TASK-S017.1.
- Ne pas ajouter de logique Asterisk. Ne pas créer de tables `ps_*`.
- FusionPBX est installé sur le serveur (DB `fusionpbx`) mais abandonné — référence technique uniquement.
- Trunks = Simple IP seulement (jamais exposés dans portail client).
- Portail client = côté ERPCRM (Portal.jsx + PortalUser) — pas dans l'admin SIPV (port 3020).

---

## Complétées

### Fondation serveur

| Task        | Module-clé       | Description                                                                       |
|-------------|------------------|-----------------------------------------------------------------------------------|
| TASK-S000.1 | audit serveur    | Audit serveur SIPV — OS, ressources, paquets disponibles                          |
| TASK-S000.2 | freeswitch       | FreeSWITCH 1.10.12 compilé et installé — sofia-sip, systemd service              |
| TASK-S000.3 | postgresql       | PostgreSQL 18 installé — DB freeswitch créée, schéma custom                      |
| TASK-S000.4 | structure projet | FastAPI async (port 8020) + React/Vite (port 3020) — même pattern ERPCRM         |

#### TASK-S000.1 [x] Audit serveur SIPV
Résultat : Ubuntu 26.04 LTS, 15 Go RAM, 98 Go disque, Python 3.14 pré-installé.
Asterisk / Kamailio / PostgreSQL / nginx / rtpengine absents au départ — serveur vierge.

#### TASK-S000.2 [x] FreeSWITCH 1.10.12
Compilé depuis sources avec GCC 15 (flags : -std=gnu11 -Wno-error).
sofia-sip 1.13.17 compilé depuis /usr/src/sofia-sip-1.13.17.
Modules désactivés : mod_shout (MP3), mod_spandsp (fax T.38).
Binaire : /usr/local/freeswitch/bin/freeswitch.
PID : /usr/local/freeswitch/run/freeswitch.pid.
Systemd : /etc/systemd/system/freeswitch.service.
FusionPBX installé sur le même serveur mais ABANDONNÉ — interface trop contre-intuitive.
DB fusionpbx laissée en place pour référence technique uniquement (dialplan, directory, IVR).

#### TASK-S000.3 [x] PostgreSQL 18
DB `freeswitch` créée. Schéma 100% custom SIPV (pas de tables FusionPBX réutilisées).
14 migrations Alembic (0001_initial → 0014_schedules) — applicables via `alembic upgrade head`.

#### TASK-S000.4 [x] Structure projet FastAPI + React
FastAPI async + SQLAlchemy + Alembic. Port 8020 backend, port 3020 frontend.
Même pattern ERPCRM : schemas Pydantic inline, get_current_user, get_db, UUID primary keys.
Backend : /home/simpleip/sipv/backend/app/
Frontend : /home/simpleip/sipv/frontend/src/

---

### Code backend / frontend

| Task       | Module-clé        | Description                                                                          |
|------------|-------------------|--------------------------------------------------------------------------------------|
| TASK-S001  | auth              | Auth — Login JWT, get_current_user, sipv_users table                                 |
| TASK-S002  | tenants sync      | Tenants — liste, détail, création, sync depuis ERPCRM via X-Api-Key                  |
| TASK-S003  | extensions        | Extensions — CRUD backend, username={account}-{ext}, liste par tenant                |
| TASK-S004  | trunks            | Trunks — CRUD backend, failover_trunk_id FK auto-référentielle (Simple IP seulement) |
| TASK-S005  | dids              | DIDs — CRUD backend, destination_type : extension/ivr/queue/voicemail/hangup         |
| TASK-S006  | routes dialplan   | Routes sortantes (dial_patterns, strip/prepend) + entrantes (DID→destination)        |
| TASK-S007  | ivr               | IVR + options (0-9/*/#) + files d'attente + ring groups + parcs d'appels             |
| TASK-S008  | voicemail         | Boîtes vocales + messages + envoi courriel (attach MP3, delete après envoi)          |
| TASK-S009  | cdr               | CDR complet + calcul coût par préfixe + import grille prix CSV + résumé paginé       |
| TASK-S010  | e911              | Adresses 911 NENA NG911 + assignation DID + alerte conformité (DIDs sans 911)        |
| TASK-S011  | provisioning      | Provisioning auto Grandstream — templates Jinja2, GET /provisioning/mac/{mac}/config |
| TASK-S012  | recordings        | Politiques enregistrement par tenant + stockage local/Dropbox/OneDrive/S3            |
| TASK-S013  | fax sms           | Fax (T.38, ATA, PDF) + SMS multi-provider (Twilio/Telnyx/Bandwidth/etc.)             |
| TASK-S014  | security          | Audit log + ACL CIDR + règles antifraude + blocage IP automatique                   |
| TASK-S015  | webhooks          | Webhooks sortants HMAC-SHA256 + delivery log + retry queue                           |
| TASK-S016  | schedules         | Horaires par tenant (règles hebdo + jours fériés + timezone) — is-open check         |
| TASK-S017  | commit changes    | Commit/rollback PendingChange — ⚠️ logique Asterisk, obsolète, remplacée par S017.1  |

#### TASK-S001 [x] Auth
sipv_users table, JWT Bearer, get_current_user dependency dans chaque endpoint.
Endpoints : POST /api/v1/auth/login, GET /api/v1/auth/me.
Fichier : backend/app/api/v1/endpoints/auth.py, models/user.py.

#### TASK-S002 [x] Tenants + sync ERPCRM
Tenant model : account_number = domain FreeSWITCH = context_prefix (format : t-{account}).
Sync depuis ERPCRM : POST /api/v1/sync/company (header X-Api-Key = settings.ERPCRM_API_KEY).
Crée ou met à jour le tenant selon account_number.
Health check : GET /api/v1/sync/status.
Fichiers : models/tenant.py, api/v1/endpoints/tenants.py, api/v1/endpoints/sync.py.

#### TASK-S003 [x] Extensions
SIPExtension model. username = {account_number}-{extension} (unique global).
Champs : extension, name, username, password, voicemail_enabled, voicemail_email,
caller_id_name, caller_id_number, record_calls, max_contacts, is_active.
⚠️ Champ asterisk_synced = legacy Asterisk → à renommer freeswitch_synced (TASK-S017.1).
Fichiers : models/sip.py (SIPExtension), api/v1/endpoints/extensions.py.

#### TASK-S004 [x] Trunks
SIPTrunk model : name, carrier_name, host, username, password, from_domain,
caller_id, failover_trunk_id (FK auto-référentielle), is_active.
⚠️ asterisk_synced = legacy → à renommer freeswitch_synced (TASK-S017.1).
Gestion Simple IP uniquement — portail client n'y a jamais accès.
Fichiers : models/sip.py (SIPTrunk), api/v1/endpoints/trunks.py.

#### TASK-S005 [x] DIDs
TenantDID model : number, label, destination_type, destination, has_911, e911_address, is_active.
destination_type enum : extension / ivr / queue / voicemail / hangup.
Fichiers : models/sip.py (TenantDID), api/v1/endpoints/dids.py.

#### TASK-S006 [x] Routes
OutboundRoute : dial_patterns, trunk_id, strip_digits, prepend, priority.
InboundRoute : did_number, destination_type, destination_id.
Failover trunk via failover_trunk_id sur SIPTrunk.
Fichiers : models/dialplan.py, api/v1/endpoints/routes.py, frontend/src/pages/RoutesPage.jsx.

#### TASK-S007 [x] IVR / Files d'attente / Groupes
IVR + IVROption (chiffre 0-9 + * + #, destination_type, destination_id).
Queue + QueueMember. RingGroup. ParkingLot.
music_on_hold sur Queue (global par défaut, override per-tenant via TASK-S033).
Fichiers : models/ivr.py, api/v1/endpoints/ivr.py, frontend/src/pages/IVRPage.jsx.

#### TASK-S008 [x] Voicemail
VoicemailBox + VoicemailMessage.
Options : email_on_new, attach_message (MP3/WAV), delete_after_email.
Fichiers : models/voicemail.py, api/v1/endpoints/voicemail.py, frontend/src/pages/VoicemailPage.jsx.

#### TASK-S009 [x] CDR + coûts
CDR model : champs FreeSWITCH complets + direction (inbound/outbound/internal) + cost + prefix_id.
RatePrefix : prefix unique, rate_per_minute, min_duration, increment — longest-prefix match.
Import grille prix : POST /api/v1/cdr/prefixes/import (CSV upsert).
Résumé (total/answered/billsec/cost) + liste paginée avec filtres + index sur tenant_id+start_time.
Fichiers : models/cdr.py, api/v1/endpoints/cdr.py, frontend/src/pages/CDRPage.jsx.

#### TASK-S010 [x] E911
E911Address : adresse civique NENA NG911, province, is_validated, carrier_reference.
DID911Assignment : DID→adresse 1:1 unique, emergency_trunk_id, alert_email.
Alerte conformité : GET /api/v1/e911/dids-without-911/tenant/{id}.
Fichiers : models/e911.py, api/v1/endpoints/e911.py, frontend/src/pages/E911Page.jsx.

#### TASK-S011 [x] Provisioning Grandstream (prioritaire)
PhoneModel : brand/model/firmware, config_template Jinja2, max_accounts, protocol http/https/tftp.
ProvisionedPhone : mac_address unique, extension_id, extra_config JSON (overrides par appareil).
GET /api/v1/provisioning/{id}/config → config rendue.
GET /api/v1/provisioning/mac/{mac}/config → sans auth (appelé directement par le téléphone).
Grandstream = prioritaire (98% clients). Yealink, Fanvil = à venir après.
Fichiers : models/provisioning.py, api/v1/endpoints/provisioning.py, frontend/src/pages/ProvisioningPage.jsx.

#### TASK-S012 [x] Enregistrements d'appels
RecordingPolicy per tenant : record_inbound/outbound/internal, retention_days,
storage_backend enum local/dropbox/onedrive/s3, storage_credentials chiffré.
CallRecording : metadata + path, expires_at calculé auto, soft-delete.
Intégration Dropbox/OneDrive = OAuth2 SDK requis, non implémenté (stub).
Fichiers : models/recording.py, api/v1/endpoints/recordings.py.

#### TASK-S013 [x] Fax + SMS
FaxLine : DID + delivery_email + use_t38 + ata_ip/model.
FaxJob : direction inbound/outbound, status pending/processing/delivered/failed, file PDF.
SMSConfig per tenant : provider enum twilio/bandwidth/telnyx/sinch/vonage/other,
api_key+secret chiffrés, from_number, webhook_url, monthly_limit.
SMSMessage : direction/status/from/to/body/provider_message_id/cost.
POST /api/v1/sms/webhook/{tenant_id} = endpoint public inbound (sans auth).
Dispatch réel vers provider = stub activable quand credentials disponibles.
Fichiers : models/fax.py, models/sms.py, api/v1/endpoints/fax.py, api/v1/endpoints/sms.py,
frontend/src/pages/FaxSMSPage.jsx.

#### TASK-S014 [x] Sécurité avancée
SecurityEvent : audit log event_type/severity/source_ip, resolve.
ACLRule : CIDR allow/deny, priority, per-tenant ou global.
FraudRule : limits calls/h, concurrent, intl/jour, block_intl/premium, alert_email, auto_block.
BlockedIP : upsert avec block_count, expires_at, unblock.
SRTP = config FreeSWITCH pjsip.conf (hors API).
Fichiers : models/security.py, api/v1/endpoints/security.py, frontend/src/pages/Security.jsx.

#### TASK-S015 [x] Webhooks sortants
WebhookEndpoint : url + secret HMAC-SHA256 + event_types CSV.
WebhookDelivery : log tentatives, next_retry_at, success.
POST /api/v1/webhooks/dispatch enregistre + met en queue.
Dispatch HTTP réel = worker background (stub pour instant).
Fichiers : models/webhook.py, api/v1/endpoints/webhooks.py.

#### TASK-S016 [x] Horaires
Schedule : timezone, closed_destination.
ScheduleRule : days_of_week CSV 0-6, open_time/close_time.
Holiday : date, recurring boolean, override_destination.
GET /api/v1/schedules/{id}/is-open vérifie heure courante vs règles + jours fériés (zoneinfo).
Fichiers : models/schedule.py, api/v1/endpoints/schedules.py, frontend/src/pages/SchedulesPage.jsx.

#### TASK-S017 [x] Commit/rollback — ⚠️ LOGIQUE ASTERISK OBSOLÈTE
PendingChange model : tenant_id, change_type, entity_type, entity_id, payload JSONB,
status (pending/applied/failed/rolled_back), error_message, applied_at, created_by.
commit.py écrivait dans ps_endpoints/ps_auths/ps_aors (tables Asterisk — inexistantes dans FreeSWITCH).
Champ asterisk_synced sur SIPExtension/SIPTrunk = legacy à remplacer par freeswitch_synced.
NE PAS UTILISER commit.py pour de nouveaux développements.
Remplacé par : TASK-S017.1 (FreeSWITCH via mod_xml_curl + ESL).
Fichiers : models/pending_change.py, api/v1/endpoints/commit.py.

---

## Backlog

### Bloc 1 — FreeSWITCH foundation (bloqueurs — faire en premier)

| Task        | Module-clé        | Description                                                                          |
|-------------|-------------------|--------------------------------------------------------------------------------------|
| TASK-S017.1 | commit freeswitch | Réécrire commit/sync pour FreeSWITCH — remplacer logique Asterisk par ESL + xml_curl|
| TASK-S020   | esl               | Connexion ESL depuis FastAPI — surveiller appels live, envoyer commandes FreeSWITCH ✓|
| TASK-S021   | mod_xml_curl      | Endpoint FastAPI servant directory XML + dialplan XML à FreeSWITCH (multi-tenant)    |

#### TASK-S017.1 [~] Commit/sync FreeSWITCH
Remplace la logique Asterisk de TASK-S017 par un cycle FreeSWITCH (ESL + mod_xml_curl).
Implémenté :
- Migration `0016_freeswitch_synced_rename` : RENAME COLUMN asterisk_synced → freeswitch_synced
  sur sip_extensions et sip_trunks (préserve les données existantes).
- models/sip.py : champ `freeswitch_synced` sur SIPExtension et SIPTrunk (remplace asterisk_synced).
- commit.py : `_apply_change_to_asterisk()` supprimée. Nouvelle `_apply_change_to_freeswitch(esl)` —
  appelle `esl.reload_xml()` (déjà présent dans core/esl.py depuis TASK-S020) une seule fois par
  commit, pas par change. Pas d'écriture locale : FreeSWITCH retire le XML à jour directement
  depuis /api/v1/xml_curl (TASK-S021) au prochain lookup. Marque freeswitch_synced=True sur
  l'extension si le reload réussit ; toutes les changes du batch échouent si le reload échoue.
- extensions.py, trunks.py, frontend/src/pages/TenantDetail.jsx : toutes les références à
  asterisk_synced mises à jour vers freeswitch_synced (cascade nécessaire trouvée pendant
  l'implémentation, pas dans la description initiale de la tâche).
Écart vs plan : PendingChange.status non étendu — c'est explicitement TASK-S023, hors scope ici.
Bugs rencontrés : aucun (syntax-check Python OK sur les 5 fichiers backend touchés).
Reste à faire [~] :
- Déployer sur le serveur SIPV (rsync — le serveur est actuellement 2 migrations en retard,
  0015 et 0016 non appliquées) puis `alembic upgrade head`.
- Valider avec un vrai commit sur un tenant test une fois FreeSWITCH + DB sync (nécessite GO
  séparé — action sur environnement partagé, pas faite dans cette session).
- models/dialplan.py (OutboundRoute/InboundRoute) a son propre champ `asterisk_synced`
  (migration 0003) — PAS touché ici, hors scope de cette tâche telle que décrite.
Dépend de : TASK-S020 (ESL) ✓, TASK-S021 (mod_xml_curl endpoint) ✓.
Fichiers modifiés : backend/alembic/versions/0016_freeswitch_synced_rename.py (nouveau),
models/sip.py, api/v1/endpoints/commit.py, api/v1/endpoints/extensions.py,
api/v1/endpoints/trunks.py, frontend/src/pages/TenantDetail.jsx.

#### TASK-S020 [x] ESL — connexion FastAPI → FreeSWITCH
Implémentation : pure asyncio (pas de greenswitch ni de lib externe — protocole ESL implémenté manuellement).
Classe `ESLClient` : `connect()`, `_read_packet()`, `api()`, `bgapi()`, `reload_xml()`,
`sofia_status()`, `sofia_contact()`, `show_registrations()`, `uuid_kill()`, `originate()`.
Singleton : `esl_startup()` / `esl_shutdown()` dans lifespan FastAPI. Dependency `get_esl()` avec reconnexion auto.
Protocole ESL : headers terminés par `\n\n` lus avec `readuntil()`, body lu avec `readexactly(Content-Length)`.
Fichiers créés : `backend/app/core/esl.py`, `backend/app/api/v1/endpoints/esl.py`.
Fichier modifié : `backend/app/main.py` (lifespan + include_router esl).
Migration : aucune.
Endpoints créés : GET /api/v1/esl/status, POST /api/v1/esl/reload,
GET /api/v1/esl/registrations, GET /api/v1/esl/registrations/tenant/{id},
GET /api/v1/esl/registration/{username}, DELETE /api/v1/esl/calls/{uuid}.
⚠️ Bug : f-string `originate` — `{{{' '.join(vars_parts)}}}` → SyntaxError
   Fix  : construire `vars_str` dans une variable séparée avant le f-string
⚠️ Bug : `\*` escape invalide en Python dans f-string → SyntaxError
   Fix  : remplacer `\*` par `\\*` dans tous les patterns regex
⚠️ Bug : `\d` escape invalide en Python dans f-string → SyntaxError
   Fix  : remplacer `\d` par `[0-9]`
Écart vs plan : greenswitch mentionné comme "lib cible" — non utilisé, asyncio natif choisi
(aucune dépendance pip supplémentaire).

#### TASK-S021 [x] mod_xml_curl endpoint
FreeSWITCH appelle FastAPI pour obtenir sa config XML dynamiquement à chaque registration/appel.
Implémentation : endpoint unique POST /api/v1/xml_curl (section lue dans le form body).
Sections gérées : `directory` (auth SIP), `dialplan` (routing), `configuration` (ivr.conf).
Fonctions clés :
- `_handle_directory()` — lookup Tenant par account_number, SIPExtension par username, XML credentials
- `_dialplan_internal(account)` — extension-to-extension, ring groups, voicemail *97/*98, routes sortantes
- `_dialplan_public(destination)` — inbound DID → extension/IVR/queue/voicemail
- `_config_ivr()` — retourne ivr.conf avec tous les menus IVR actifs
- `_bridge(username, domain)` → `sofia/internal/{username}@{domain}`
Context naming : `internal-{account_number}`.
Fichier créé : `backend/app/api/v1/endpoints/xml_curl.py`.
Fichier modifié : `backend/app/main.py` (include_router xml_curl).
Migration : aucune.
⚠️ Bug : `selectinload(InboundRoute.__class__)` — passe le type Python, pas une relation → erreur SQLAlchemy
   Fix  : supprimé entièrement (pas nécessaire pour ce query)
⚠️ Bug : `\*97` escape invalide dans f-string → SyntaxError
   Fix  : remplacé par `\\*97`
⚠️ Bug : `\d+` escape invalide dans f-string → SyntaxError
   Fix  : remplacé par `[0-9]+`
Écart vs plan : un seul endpoint POST (pas /directory et /dialplan séparés) — FreeSWITCH
envoie `section=` dans le body, un seul handler lit le champ et dispatch.

---

### Bloc 2 — Modèle de données

| Task       | Module-clé       | Description                                                                          |
|------------|------------------|--------------------------------------------------------------------------------------|
| TASK-S022  | contact link     | Lien SIPExtension ↔ contact ERPCRM (vérif/cocher checkbox/créer si absent)          |
| TASK-S023  | sync states      | Sync states étendus sur PendingChange + message client retenu                        |
| TASK-S024  | impact analysis  | Analyse d'impact avant delete/modify — bloquer si dépendances non résolues           |
| TASK-S025  | sync order       | Sync queue ordonné par dépendances (contacts→extensions→...→facturation)             |
| TASK-S026  | audit trail      | [~] Infrastructure audit complète — câblage partiel (extensions seulement)           |

#### TASK-S022 [ ] Lien extension ↔ contact ERPCRM
Ajouter erpcrm_contact_id (UUID nullable) sur SIPExtension (migration Alembic).
Flux création extension dans SIPV :
1. Chercher contact ERPCRM via GET {ERPCRM_HOST}/api/v1/contacts?search={name}
2. Si trouvé → PATCH /contacts/{id} pour cocher sipv_sync=true + enregistrer erpcrm_contact_id
3. Si non trouvé → POST /contacts pour créer avec sipv_sync=true, récupérer l'ID créé
Flux suppression extension : appeler ERPCRM PATCH /contacts/{id} pour décocher sipv_sync.
Flux changement nom contact ERPCRM → webhook ERPCRM→SIPV → mise à jour caller_id_name + freeswitch_synced=false (re-sync à planifier).
Dépend de : TASK-S037 (champs sipv_sync + extension_number sur Contact ERPCRM).
Fichiers modifiés : models/sip.py, api/v1/endpoints/extensions.py.

#### TASK-S023 [ ] Sync states étendus
Migration Alembic — étendre PendingChange.status :
draft / saved / pending / synced / error / blocked_by_impact / approval_required / cancelled
Message client affiché dans portail : "Vos changements sont enregistrés. Ils seront synchronisés avec le système téléphonique dans un délai maximal d'une heure."
Simple IP peut déclencher sync manuelle (bouton admin) ou immédiate si changement propre techniquement.
Fichier modifié : models/pending_change.py + migration Alembic.

#### TASK-S024 [ ] Analyse d'impact
Avant tout DELETE ou PATCH sur : extension, groupe, IVR, DID, horaire.
Vérifier toutes les dépendances :
- Extension → utilisée dans groupe / IVR option / route entrante / voicemail forward
- Groupe → utilisé dans IVR option / route entrante
- IVR → utilisé dans route entrante / option d'un autre IVR
- Horaire → assigné à IVR / route entrante
- DID → assigné à route entrante / E911
Réponse API : liste des dépendances + actions proposées (modifier la destination / choisir autre / annuler).
Blocage : PendingChange → status=blocked_by_impact tant que chaque impact n'est pas résolu.
Pas de sauvegarde → pas de sync → pas d'application FreeSWITCH tant que bloqué.

#### TASK-S025 [ ] Sync queue ordonné
Ordre d'application des PendingChange lors du commit :
1. Contacts / noms liés (caller_id_name)
2. Extensions (directory FreeSWITCH)
3. Boîtes vocales
4. Renvois d'appels
5. Messages audio / MOH / prompts
6. Groupes / ring groups
7. IVR + options
8. Horaires
9. Routes entrantes
10. DIDs (destination assignée)
11. CDR / usage
12. Facturation
Raison : groupes dépendent des extensions, IVR dépend des groupes et des messages audio,
routes dépendent des IVR, facturation dépend des services actifs.

#### TASK-S026 [~] Audit trail complet
Infrastructure complète en place. Câblage partiel (extensions.py seulement — voir reste à faire).
Fichiers créés :
- `backend/app/models/audit_log.py` — modèle AuditLog (table `audit_logs`)
- `backend/app/core/audit.py` — helper `log_audit()` + `get_client_ip()` (supporte X-Forwarded-For)
- `backend/app/api/v1/endpoints/audit.py` — GET /api/v1/audit + GET /api/v1/audit/entity/{type}/{id}
Fichiers modifiés : `models/__init__.py`, `main.py`, `api/v1/endpoints/extensions.py`.
Migration : `0015_audit_log.py` (révision 0015_audit_log).
Champs implémentés : id, tenant_id, entity_type, entity_id, entity_label, action,
old_data JSONB, new_data JSONB, changed_by (email), changed_by_ip, created_at.
Snapshot extensions : `_snapshot()` dans extensions.py — exclut le mot de passe,
note `password_changed: true` si modifié.
Endpoints : GET /api/v1/audit (filtres : tenant_id, entity_type, action, changed_by, date_from, date_to, limit, offset),
GET /api/v1/audit/entity/{entity_type}/{entity_id}.
Câblé dans : extensions.py (create ✓, update ✓, delete ✓).
Écarts vs plan :
- Nom table : `audit_logs` (pas `SIPAuditLog`)
- Champs omis : `source` (portail_admin/api/webhook), `sync_state`, `erpcrm_contact_id` — simplification volontaire
- `who` renommé `changed_by` (email), `old_value`/`new_value` → `old_data`/`new_data`
- `entity_label` ajouté (nom lisible au moment du changement, pas dans le plan)
Reste à faire [~] — câbler `log_audit()` dans :
- `api/v1/endpoints/trunks.py` (create, update, delete)
- `api/v1/endpoints/dids.py` (create, update, delete)
- `api/v1/endpoints/ivr.py` (IVR, Queue, RingGroup — create, update, delete)
- `api/v1/endpoints/tenants.py` (create, update)
- `api/v1/endpoints/commit.py` (action commit/rollback)
- Autres endpoints selon priorité

---

### Bloc 3 — UX UCM (admin SIPV — Simple IP uniquement, port 3020)

| Task        | Module-clé    | Description                                                                     |
|-------------|---------------|---------------------------------------------------------------------------------|
| TASK-S018   | ux extension  | Fiche extension unifiée — codec, voicemail, provisioning, horaires, statut live |
| TASK-S018.1 | ux did        | Fiche DID unifiée — routage, horaires, destination, E911 sur une seule page     |
| TASK-S018.2 | ux trunk      | Fiche trunk unifiée — carrier, credentials, failover, statut live               |

#### TASK-S018 [~] Fiche extension unifiée (style UCM Grandstream)
Tout ce qui touche une extension = sur une seule page.
Implémenté (backé par des endpoints existants, aucun champ inventé) :
- Statut live : Registered/Unregistered via GET /api/v1/esl/registration/{username}
- Infos SIP : username (lecture seule), régénération mot de passe (nouvel endpoint
  POST /api/v1/extensions/{ext_id}/regenerate-password — génère server-side via
  secrets.token_urlsafe, affiché une seule fois côté UI), nom, caller ID, max_contacts,
  enregistrement d'appels, actif/inactif — PUT /api/v1/extensions/{ext_id}
- Voicemail : lecture seule (email, notifications, pièce jointe) — trouvé par filtrage
  client-side de GET /voicemail/tenant/{id} sur extension_id
- Provisioning : lecture seule (MAC, emplacement, dernière connexion) — filtrage
  client-side de GET /provisioning/tenant/{id} sur extension_id
Nouvel endpoint backend nécessaire ajouté : GET /api/v1/extensions/{ext_id} (fetch unitaire —
n'existait pas, seule la liste par tenant existait).
Fichiers : frontend/src/pages/ExtensionDetail.jsx (nouveau), App.jsx (route /extensions/:id),
TenantDetail.jsx (lien cliquable sur le numéro d'extension), extensions.py (2 endpoints ajoutés).
Ajouté ensuite (2026-07-17, sur autorisation explicite — codec et horaires implémentés) :
- Migration `0017_extension_codec_schedule` : ajoute `codec` (String(10) nullable, null =
  pas de restriction) et `schedule_id` (UUID nullable, FK schedules.id ON DELETE SET NULL)
  sur sip_extensions.
- models/sip.py : champs `codec`, `schedule_id` sur SIPExtension.
- extensions.py : codec + schedule_id ajoutés à ExtOut/ExtCreate/ExtUpdate/_out/_snapshot.
  Horaires réutilise le Schedule existant (TASK-S016) — pas de nouveau modèle, pas de
  "destination renvoi hors-heures" dupliquée (déjà sur Schedule.closed_destination).
- xml_curl.py : `_user_xml()` émet la variable FreeSWITCH `absolute_codec_string`
  (mapping ulaw→PCMU, alaw→PCMA, g722→G722, g729→G729) seulement si `ext.codec` est défini —
  comportement inchangé pour les extensions existantes (codec=null par défaut).
- ExtensionDetail.jsx : select codec dans Infos SIP ; section Horaires devenue fonctionnelle
  (choix d'un Schedule du tenant, affiche la destination hors-heures du schedule sélectionné).
Toujours non fait, hors scope de cette session :
- Lien ERPCRM (contact lié, sync nom) : dépend de TASK-S022 (bloqué sur l'auth ERPCRM,
  discussion en cours avec l'utilisateur) — section UI présente, marquée "à venir".
- DND / appels en cours en direct : pas juste un champ, nécessite de nouvelles méthodes
  ESLClient (ex: `show channels`) — plus gros que l'ajout d'un champ, pas fait ici.
- Voicemail et Provisioning restent en lecture seule sur cette page (édition déjà possible
  via VoicemailPage.jsx / ProvisioningPage.jsx) — pas dupliqué le formulaire.
Build frontend vérifié (`npm run build` OK) après chaque ajout, syntax-check Python OK.
Dépend de : TASK-S020 (statut live ESL) ✓, TASK-S016 (schedules, réutilisé) ✓.

#### TASK-S018.1 [ ] Fiche DID unifiée
Tout ce qui touche un DID = sur une seule page :
Numéro, carrier, type, destination principale, horaires (destination selon heure),
E911 assigné, enregistrement activé, historique appels (CDR filtrés sur ce DID).

#### TASK-S018.2 [ ] Fiche trunk unifiée
Tout ce qui touche un trunk = sur une seule page :
Carrier, host, port, username/password, from_domain, caller ID sortant,
failover trunk assigné, routes utilisant ce trunk,
statut live (UP/DOWN via ESL sofia status).

---

### Bloc 4 — Portail client (côté ERPCRM — port 3010)

| Task       | Module-clé         | Description                                                                        |
|------------|--------------------|------------------------------------------------------------------------------------|
| TASK-S027  | portal permissions | Permissions téléphoniques granulaires sur PortalUser ERPCRM                       |
| TASK-S028  | portal mon poste   | Section "Mon poste" dans portail ERPCRM — statut live, DND, renvois, VM, CDR      |
| TASK-S029  | portal gestion tél | Section "Gestion téléphonique" dans portail ERPCRM — granulaire par permission     |
| TASK-S030  | session lock       | Session gestionnaire unique — lock, timeout 30min, blocage user si actif           |
| TASK-S031  | code temporaire    | Code unique gestionnaire → accès ticket limité sans accès gestion complète         |

#### TASK-S027 [ ] Permissions téléphoniques PortalUser ERPCRM
Migration Alembic ERPCRM — ajouter champs boolean sur portal_users :
can_view_own_extension, can_edit_extension_name, can_edit_call_forward,
can_edit_dnd, can_edit_voicemail, can_view_own_cdr, can_view_voicemail_messages,
can_receive_alerts, can_manage_telephony, can_manage_ivr, can_manage_groups,
can_manage_audio_prompts, can_view_company_cdr.
Validation serveur systématique : même si UI masquée, le backend SIPV refuse si permission absente.
Fichier modifié : /home/simpleip/erpcrm/backend/app/models/portal.py.

#### TASK-S028 [ ] Portal "Mon poste"
Visible si can_view_own_extension = true.
Contenu affiché selon permissions individuelles :
- Statut d'enregistrement live (Registered / Unregistered) via ESL → API SIPV → portail
- DND toggle (si can_edit_dnd)
- Numéro extension + caller ID affiché
- Renvoi inconditionnel / sur occupé / sans réponse / follow-me (si can_edit_call_forward)
- Options voicemail — activé, email, attach (si can_edit_voicemail)
- Messages vocaux (si can_view_voicemail_messages)
- CDR personnel (si can_view_own_cdr)
Fichier modifié : /home/simpleip/erpcrm/frontend/src/pages/Portal.jsx (section ajoutée).

#### TASK-S029 [ ] Portal "Gestion téléphonique"
Visible si can_manage_telephony = true.
Fonctions disponibles selon permissions granulaires :
- Liste postes du tenant, modifier noms + voicemail + renvois (can_manage_telephony)
- Gérer IVR et options (can_manage_ivr)
- Gérer groupes d'appels / ring groups (can_manage_groups)
- Gérer prompts audio et MOH (can_manage_audio_prompts)
- Voir CDR compagnie selon droits (can_view_company_cdr)
Éléments TOUJOURS protégés (Simple IP seulement, jamais exposés) :
trunks, routes sortantes, DIDs principaux, E911, sécurité, config fournisseur.
Validation serveur : le backend SIPV vérifie les permissions à chaque requête,
indépendamment de ce que le portail affiche ou cache.
Fichier modifié : /home/simpleip/erpcrm/frontend/src/pages/Portal.jsx (section ajoutée).

#### TASK-S030 [ ] Session gestionnaire lock
Une seule session gestionnaire active par tenant à la fois.
Timeout inactivité : 30 min par défaut (configurable par Simple IP dans settings tenant).
Si gestionnaire connecté + utilisateur ordinaire tente modification :
→ Message : "Modification temporairement indisponible. Le gestionnaire [nom] est connecté au portail. Veuillez le contacter pour cette modification."
Table cible SIPV : SIPManagerSession (tenant_id, portal_user_id, started_at, last_active_at, is_active).
Heartbeat côté portail pour maintenir last_active_at à jour.

#### TASK-S031 [ ] Code temporaire gestionnaire
Gestionnaire génère un code unique à durée limitée (ex: 4h).
Le code permet à un utilisateur sans privilège de soumettre une demande ciblée (comme un ticket limité).
Ne donne PAS accès à la gestion complète.
Simple IP traite la demande résultante.
Table cible : SIPTempCode (code UUID court, tenant_id, created_by_portal_user_id,
expires_at, used_at, action_type, is_used).

---

### Bloc 5 — Infrastructure et services

| Task       | Module-clé     | Description                                                                          |
|------------|----------------|--------------------------------------------------------------------------------------|
| TASK-S033  | moh            | MOH global par défaut + override par tenant (upload ou sélection)                   |
| TASK-S034  | alertes        | Alertes trunk/extension down — webhook + courriel + SMS, Simple IP + client          |
| TASK-S037  | contact erpcrm | Champs contact ERPCRM : sipv_sync, extension_number, phone_cell, phone_other         |
| TASK-S038  | health check   | Health check ERPCRM↔SIPV + bouton sync manuelle + alerte connexion perdue            |

#### TASK-S033 [ ] MOH — Music on Hold
Fichier MOH global par défaut (upload Simple IP — s'applique à tous les tenants).
Champ moh_file (nullable) sur Tenant — si null, fallback sur fichier global.
Interface upload dans TenantDetail (admin SIPV).
Référencé dans Queue.music_on_hold et dans le dialplan XML généré par mod_xml_curl.
Fichier modifié : models/tenant.py + migration Alembic.

#### TASK-S034 [ ] Alertes trunk/extension
Événements surveillés via ESL : trunk DOWN, extension unregistered, perte registration, HEARTBEAT absent.
Destinations configurables : webhook (TASK-S015) + courriel + SMS.
Simple IP reçoit toujours (alerte systématique).
Client reçoit si option activée sur le poste (can_receive_alerts) ou sur le tenant.
Table cible : SIPAlertConfig (tenant_id, event_type, notify_simpleip, notify_client,
email, sms_number, webhook_enabled).

#### TASK-S037 [x] Champs contact ERPCRM (nécessaire pour TASK-S022)
Lien ERPCRM : TASK-016.
Fait (TASK-016 ERPCRM) :
- `sipv_sync` bool (défaut false) ajouté sur Contact ✓
- `phone_other` str nullable ajouté sur Contact ✓
- Migration ERPCRM : `g8h9i0j1k2l3_add_contact_sipv_fields.py`
- ContactDetail.jsx : checkbox "Synchroniser avec SIPV" + badge "SIP actif" + champ "Autre numéro" ✓
- ContactOut/ContactCreate/ContactUpdate mis à jour ✓
Vérifié le 2026-07-17 (session SIPV) — les deux points encore ouverts sont déjà couverts :
- `extension_number` : le champ `extension` existant sur Contact est déjà affiché/éditable
  dans ContactDetail.jsx sous le label "Poste SIP" (ligne 229) — pas de champ distinct nécessaire.
- `phone_cell` : le champ `mobile` existant est déjà affiché/éditable sous le label
  "Cellulaire" (ligne 230) — couvre le besoin.
Aucun code ajouté (pas de doublon de champ). TASK-S022 n'est plus bloquée sur ce point.

#### TASK-S038 [ ] Health check + sync manuelle + alerte connexion
Endpoint GET /api/v1/health/erpcrm → SIPV vérifie joignabilité ERPCRM (settings.ERPCRM_HOST).
Endpoint GET /api/v1/health/sipv → ERPCRM vérifie joignabilité SIPV (settings.SIPV_API_URL).
Bouton "Synchronisation" dans admin SIPV → déclenche vérification cohérence complète :
- Extensions orphelines (dans SIPV sans contact ERPCRM lié)
- Contacts désynchronisés (sipv_sync=true mais pas d'extension SIPV correspondante)
- Tenants sans compagnie ERPCRM liée
- Noms différents entre les deux systèmes
Rapport de résultats affiché + option de corriger chaque écart.
Alerte si connexion perdue : webhook + courriel + SMS (même destinations que TASK-S034).

---

### Bloc 6 — Facturation

| Task       | Module-clé   | Description                                                                              |
|------------|--------------|------------------------------------------------------------------------------------------|
| TASK-S032  | billing link | SIPV → ERPCRM billing triggers (service créé/modifié/retiré → lignes facturation prorata)|

#### TASK-S032 [ ] Billing triggers SIPV → ERPCRM
Événements déclencheurs côté SIPV : création/retrait extension, ajout/retrait DID,
ajout/retrait numéro 1-800, activation/désactivation service payant.
SIPV appelle ERPCRM : POST {ERPCRM_HOST}/api/v1/billing/sipv-event (header X-Api-Key).
ERPCRM crée/ajuste/retire lignes de facturation récurrentes avec calcul prorata.
Services facturables : extensions, DIDs, 1-800, options payantes, services récurrents.
Usage facturable (1-800, international, minutes) : remonté depuis CDR (TASK-S009).

---

### Bloc 7 — Validation E2E

| Task       | Module-clé | Description                                                                              |
|------------|------------|------------------------------------------------------------------------------------------|
| TASK-S036  | poc e2e    | POC bout en bout — 10 étapes validation premier jalon FreeSWITCH opérationnel            |

#### TASK-S036 [ ] POC bout en bout — premier jalon
Valide que l'architecture complète fonctionne de bout en bout.
Étapes dans l'ordre :
1. Créer compagnie ERPCRM → déclenche création tenant SIPV automatique (sync/company)
2. Créer contact ERPCRM + cocher sipv_sync → vérifier lien dans SIPV
3. Créer extension depuis SIPV → vérifier contact ERPCRM mis à jour (sipv_sync coché, extension_number renseigné)
4. Commit changements → vérifier que mod_xml_curl sert directory.xml correct pour ce tenant
5. Enregistrer softphone avec credentials extension → vérifier "Registered" via ESL
6. Appel interne entre deux extensions du même tenant → vérifier CDR créé en DB
7. Vérifier isolation : extension tenant A ne peut pas joindre extension tenant B
8. Appel entrant sur DID → IVR → extension → vérifier CDR + routage correct
9. Portail ERPCRM "Mon poste" → statut live affiché, CDR personnel visible selon permissions
10. Alerte : interrompre connexion FreeSWITCH → vérifier alerte reçue (courriel/SMS Simple IP)
Dépend de : TASK-S017.1, TASK-S020, TASK-S021, TASK-S022, TASK-S027, TASK-S028, TASK-S037.

---

## Ordre recommandé d'exécution (backlog)

```
S037  → S022  (contact ERPCRM en premier — S022 en dépend)
S020  → S021  → S017.1  (FreeSWITCH foundation — bloqueurs)
S023  → S024  → S025  → S026  (modèle données)
S018  → S018.1 → S018.2  (UX UCM admin)
S027  → S028  → S029  → S030  → S031  (portail client)
S033  → S034  → S038  (infrastructure)
S032  (facturation)
S036  (POC E2E — dernier)
```
