# SIPV — Carte du projet pour Claude

## Stack
- **Backend** : FastAPI (async) + SQLAlchemy + PostgreSQL, port 8020
- **Frontend** : React + Vite, port 3020
- **Moteur SIP** : FreeSWITCH 1.10.12 (sur 192.168.1.55)
- **Auth** : JWT Bearer token, `get_current_user` dans chaque endpoint
- **Env** : `settings.SIPV_HOST`, `settings.ERPCRM_HOST` — jamais d'IPs en dur
- **ESL** : FreeSWITCH Event Socket — lib cible : `greenswitch` ou `esl`

## ⚠️ Ne pas faire
- Ne pas écrire dans des tables `ps_endpoints`, `ps_auths`, `ps_aors` (Asterisk PJSIP, abandonné)
- Ne pas utiliser le champ `asterisk_synced` pour de nouvelles features (legacy à remplacer)
- Ne pas réintroduire FusionPBX ou FreePBX

## Arborescence backend `/home/simpleip/sipv/backend/app/`
```
main.py                  — FastAPI app, tous les routers enregistrés
core/
  config.py              — settings (pydantic-settings)
  database.py            — engine async, Base, get_db()
  security.py            — JWT helpers
models/
  tenant.py              — Tenant (account_number = domain FreeSWITCH)
  sip.py                 — SIPExtension, SIPTrunk, TenantDID
  user.py                — User
  dialplan.py            — DialplanRoute
  ivr.py                 — IVR, Queue, RingGroup
  voicemail.py           — Voicemail
  cdr.py                 — CDR
  e911.py                — E911
  provisioning.py        — DeviceProvisioning
  recording.py           — Recording
  schedule.py            — Schedule
  security.py            — SecurityRule
  sms.py                 — SMS
  fax.py                 — Fax
  webhook.py             — Webhook
  pending_change.py      — PendingChange (commit system)
api/v1/endpoints/
  auth.py                — /api/v1/auth
  tenants.py             — /api/v1/tenants
  extensions.py          — /api/v1/extensions
  trunks.py              — /api/v1/trunks
  dids.py                — /api/v1/dids
  routes.py              — /api/v1/routes
  ivr.py                 — /api/v1/ivr
  voicemail.py           — /api/v1/voicemail
  cdr.py                 — /api/v1/cdr
  e911.py                — /api/v1/e911
  provisioning.py        — /api/v1/provisioning
  recordings.py          — /api/v1/recordings
  fax.py                 — /api/v1/fax
  sms.py                 — /api/v1/sms
  security.py            — /api/v1/security
  webhooks.py            — /api/v1/webhooks
  schedules.py           — /api/v1/schedules
  commit.py              — /api/v1/changes (commit/rollback — ⚠️ à réécrire pour FreeSWITCH)
  sync.py                — /api/v1/sync (reçoit push depuis ERPCRM)
```

## Multi-tenant
- `account_number` dans ERPCRM companies = domain FreeSWITCH = `context_prefix` dans Tenant
- Chaque client = un tenant isolé

## Connexion ERPCRM ↔ SIPV
- ERPCRM pousse les compagnies via `/api/v1/sync/company` (clé API dans header)
- `settings.ERPCRM_API_KEY` pour authentifier les appels sync

## Règles absolues
- GO obligatoire avant tout code
- Lire `TASKSIPV.md` EN PREMIER avant toute intervention
- Zéro supposition — demander si incertain
- Implémenter SEULEMENT ce qui est demandé
- Jamais d'IPs codées en dur
- Ne pas modifier un module existant sans demande explicite

## Convention TASKSIPV.md
- TASK-SXXX = création initiale d'un module SIPV
- TASK-SXXX.Y = ajout ou fix sur ce module
- Chercher le module dans TASKSIPV.md avant d'écrire une nouvelle entrée
