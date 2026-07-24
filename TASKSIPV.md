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
- **Déploiement (2026-07-18)** : les 18 migrations Alembic (0001→0018) ont été appliquées pour
  la première fois sur le serveur réel (192.168.1.55, DB `sipv`) — elle était vide avant ça,
  aucune migration n'avait jamais tourné malgré du code écrit et documenté [x] depuis des
  semaines. Backend redémarré (`uvicorn` via nohup/setsid, pas de service systemd — à
  considérer si des redémarrages serveur doivent survivre). `/api/health` répond OK.
  ⚠️ Bug trouvé et corrigé dans 0009_recordings.py, 0010_fax.py, 0011_sms.py : chaque
  migration faisait `op.execute("CREATE TYPE ... AS ENUM")` PUIS utilisait `sa.Enum(...,
  name=...)` sur une colonne du même create_table — SQLAlchemy recrée le type
  automatiquement pour toute Enum rencontrée dans un create_table, causant
  `DuplicateObjectError`. Fix : `op.execute("CREATE TYPE...")` supprimé, laissé sa.Enum
  créer le type lui-même (comportement par défaut). Aurait bloqué N'IMPORTE QUEL déploiement
  frais de ce projet — jamais détecté avant car jamais testé de bout en bout.

- **Validation E2E partielle (2026-07-18)** — TASK-S036, première tentative réelle.
  Tenant test créé (t1001 = Simple IP inc., via le nouveau checkbox ERPCRM TASK-022),
  2 extensions test créées (100, 101). Chaîne de bugs trouvés et corrigés dans l'ordre :

  1. **Pare-feu SIPV bloquait port 8020** — INPUT policy DROP, seul `lo` autorisé, rien
     n'ouvrait 8020 pour ERPCRM (192.168.1.9). Ni `/sync/company` ni le nouveau lien
     contacts n'ont JAMAIS pu fonctionner à travers le réseau avant ce fix.
     Fix : `iptables -A INPUT -p tcp -s 192.168.1.9 --dport 8020 -j ACCEPT` + persisté
     (`netfilter-persistent save`).
  2. **bcrypt 5.0.0 incompatible avec passlib 1.7.4** — `hash_password()`/`verify_password()`
     plantent (bug connu, passlib jamais mis à jour pour bcrypt>=4.1). Cassait la création
     de tout compte SIPV (aucun n'existait encore). Fix : `pip install bcrypt==4.0.1`
     (épinglé dans un futur requirements.txt si un jour créé — actuellement aucun côté SIPV).
     Même fix appliqué côté ERPCRM par prudence (bug intermittent constaté là aussi,
     requirements.txt mis à jour, service redémarré).
  3. **Frontend SIPV : bug de login** — App.jsx postait vers `/auth/token` (form-urlencoded,
     style OAuth2) alors que le backend n'expose que `POST /auth/login` (JSON). Corrigé.
     Découverte séparée : le frontend admin SIPV (dist/) n'est de toute façon PAS déployé
     sur le serveur (pas de nginx, pas de service) — testé uniquement via API/curl pour
     cette session.
  4. **mod_xml_curl jamais compilé** — commenté dans modules.conf au moment du build source
     (`/usr/src/freeswitch-1.10.12`). Toute l'architecture "FreeSWITCH tire sa config de
     SIPV" reposait sur un module absent. Compilé depuis les sources déjà présentes
     (`make && sudo make install` dans `src/mod/xml_int/mod_xml_curl`), ajouté à
     `modules.conf.xml`, gateway configuré dans `xml_curl.conf.xml`
     (`http://127.0.0.1:8020/api/v1/xml_curl`, bindings directory|dialplan|configuration).
  5. **Profils sofia internal + external en collision sur le port 5060** — aucun des deux
     n'avait de port explicite dans vars.xml, tombaient tous les deux sur le défaut 5060 ;
     "internal" perdait la course au démarrage et ne bindait jamais. Fix : ports explicites
     ajoutés (`internal_sip_port=5060`, `external_sip_port=5080`).
  6. **ACL `apply-inbound-acl=domains` bloquait tout REGISTER** — cette ACL vanilla
     n'autorise que les IP source déclarées via `cidr=` par utilisateur dans l'annuaire
     (on n'en déclare aucune) ; `default="deny"` ⇒ tout REGISTER rejeté avant même la
     vérification du mot de passe. Commentée dans internal.xml.
  7. **Réglage documenté mais jamais appliqué** — `xml-curl-use-dynamic-hash=false`,
     mentionné dans le docstring de xml_curl.py comme requis, absent d'internal.xml.
     Ajouté (impact réel non isolé du point 6, mais gardé par cohérence avec la doc).
  8. **Le vrai bug applicatif** — FreeSWITCH envoie le username d'auth avec un `@` en
     suffixe (`t1001-100@`, confirmé via `xml_curl debug_on` + inspection du POST reçu :
     `'user': 't1001-100@'`). `_handle_directory()` comparait ce username brut contre
     `SIPExtension.username` ("t1001-100", sans @) → jamais de match → "not found" →
     403 systématique. Fix : `username = form.get("user", "").split("@")[0]`.

  **Résultat final — TOUT VALIDÉ** (`sipsak` a un bug propre de formatage du digest qui
  masquait le succès réel ; `baresip`, deux instances séparées = deux "vrais" postes
  indépendants, confirme que tout fonctionne) :
  - ✅ **Enregistrement SIP** : les 2 extensions s'enregistrent avec 200 OK
    (`sofia status profile internal reg` confirme les contacts).
  - ✅ **Appel interne entre postes** : connecté, RTP établi
    (`stream: incoming rtp for 'audio' established`).
  - ✅ **CDR créé en DB** après l'appel (`src=t1001-100, dst=101, direction=inbound,
    disposition=ORIGINATOR_CANCEL` sur le test avec raccrochage manuel).

  4 bugs supplémentaires trouvés et corrigés pour arriver à l'appel qui fonctionne
  (au-delà des 8 premiers listés plus haut pour l'enregistrement) :

  9. **`_handle_dialplan` lisait des noms de champs qui n'existent jamais en pratique**
     (`context`, `destination_number`) — un vrai lookup dialplan FreeSWITCH
     (`mod_dialplan_xml`) envoie un événement complet avec `Caller-Context`,
     `Caller-Destination-Number`, `variable_sip_from_host`, etc. (confirmé par capture
     réelle). Le code n'avait jamais reçu les bonnes données, même avant cette session —
     jamais testé en vrai avant.
  10. **Contexte "public" du profil "internal" entrait en collision avec le fichier
      statique `dialplan/public.xml`** (vanilla FreeSWITCH, prioritaire sur mod_xml_curl).
      Fix : nouveau contexte dédié `sipv-internal` sur le profil (au lieu de "public"),
      qui ne collisionne avec aucun fichier statique — force TOUJOURS le passage par
      notre backend. Le tenant est déterminé au début du routage via le domaine
      d'origine de l'appelant (`variable_sip_from_host`), pas via `user_context`
      (qui ne se propage pas de façon fiable au canal appelant — jamais élucidé
      pourquoi, contourné plutôt que résolu).
  11. **Le XML `<context name="...">` retourné doit matcher EXACTEMENT le contexte
      demandé** (`Caller-Context`) — FreeSWITCH rejette sinon la réponse comme
      "not found" même si elle contient un dialplan par ailleurs valide. `_dialplan_internal`
      prend maintenant un paramètre `requested_context` pour ça.
  12. **`_bridge()` utilisait `sofia/internal/user@domain`** où `domain` = notre tenant
      (ex: "t1001") — FreeSWITCH tentait de RÉSOUDRE "t1001" comme un nom DNS
      (`503 DNS Error` systématique), au lieu d'utiliser l'enregistrement existant
      (confirmé fonctionnel via `sofia_contact`). Fix : `user/user@domain`, qui passe
      par le `dial-string` du domaine (déjà présent dans notre XML directory depuis le
      début, jamais utilisé). C'est exactement l'indice donné par l'utilisateur
      ("mon serveur actuel vérifie si c'est interne au début du routage").
  13. **`mod_xml_cdr` n'avait jamais d'URL configurée** (POST désactivé par défaut) et
      **aucun endpoint n'existait pour recevoir les CDR** — jamais géré depuis le début
      du projet. Nouveau `POST /api/v1/cdr/ingest` (parse le XML de mod_xml_cdr,
      cherche le tenant via `sip_from_host`, insère en DB). `xml_cdr.conf.xml` configuré
      (`url` + `encode=textxml` pour un parsing XML direct côté SIPV).

  **Changement d'infrastructure durable** : `sipv-backend` tournait en `nohup`/`setsid`
  manuel (pas fiable — mourait souvent entre deux commandes SSH pendant cette session).
  Remplacé par un vrai service systemd (`/etc/systemd/system/sipv-backend.service`,
  `enable --now`, `Restart=on-failure`) — survit maintenant à un reboot serveur et aux
  redémarrages nécessaires pour appliquer du nouveau code.

  Nettoyage effectué en fin de session : `xml_curl debug_on`/siptrace désactivés, loglevel
  remis à warning, fichiers temp `/tmp/*.tmp.xml` supprimés, entrée `/etc/hosts` de test
  retirée. Comptes de test restants dans la DB (tenant t1001 réutilise la vraie compagnie
  Simple IP inc. — voulu, confirmé par l'utilisateur ; extensions 100/101 ; user SIPV
  `test@simpleip.tel`) — pas nettoyés, à décider avec l'utilisateur. Contacts ERPCRM
  "Test Un"/"Test Deux" créés automatiquement par le lien S022, maintenant rattachés à
  la compagnie Simple IP dans ERPCRM (demandé par l'utilisateur).

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
| TASK-S003.1| tls postes        | TLS sur profil internal + transport impose par poste (udp/tcp/tls choisi, defaut tls) ✓|
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

#### TASK-S003.1 [x] TLS sur le profil internal + champ transport par poste
Demande de l'utilisateur : connexions sécurisées pour les postes (extensions) —
trunks reportés en attente de confirmation ISP sur le support TLS. Puis précision :
les 3 transports (udp/tcp/tls) doivent être disponibles au choix PAR POSTE, avec
TLS par défaut — le transport choisi doit être imposé (pas juste informatif), une
tentative de connexion avec un autre transport doit être refusée.
Fait côté serveur FreeSWITCH (config non versionnée, voir ci-dessous) :
- `vars.xml` : `internal_ssl_enable=true`, `internal_tls_port=5061`,
  `sip_tls_version=tlsv1.2`, `sip_tls_ciphers=ALL:!ADH:!LOW:!EXP:!MD5:@STRENGTH`
- `sip_profiles/internal.xml` : `tls-cert-dir` pointé vers `$${internal_ssl_dir}`
  (déjà = `$${conf_dir}/tls`)
- Certificat auto-signé généré dans `/usr/local/freeswitch/conf/tls/`
  (agent.pem, cafile.pem, dh2048.pem, CN=sipv.simpleip.local, 10 ans).
  `tls-verify-policy=none` → pas de blocage client sur cert auto-signé.
  ⚠️ À remplacer par un vrai certificat (Let's Encrypt ou fourni par le client)
  si des postes se connectent depuis l'extérieur avec vérification stricte.
- Profil `internal` confirmé actif sur les 3 transports simultanément :
  UDP+TCP sur 5060, TLS sur 5061 (vérifié via `sofia status profile internal`
  + `ss -tulnp` + handshake `openssl s_client`).
- `tls-only=false` (déjà présent) → TLS n'exclut pas UDP/TCP, les 3 coexistent.
Fait côté application :
- `SIPExtension.transport` (udp/tcp/tls, défaut `tls`, migration 0019) — imposé,
  pas juste informatif. Exposé dans `ExtOut`/`ExtCreate`/`ExtUpdate`, sélecteur
  ajouté sur `ExtensionDetail.jsx` avec note explicite. Postes créés par défaut
  en `tls`.
- `xml_curl.py` `_handle_directory()` : à chaque REGISTER (`sip_auth_method ==
  "REGISTER"`), compare le champ `sip_via_protocol` envoyé par FreeSWITCH
  (udp/tcp/tls — confirmé par test réel avec baresip, présent uniquement lors
  du sip_auth de REGISTER) au `transport` configuré pour le poste. Si différent
  → retourne NOT_FOUND (FreeSWITCH répond 403 Forbidden au client). Le check
  est limité à `sip_auth_method == "REGISTER"` pour ne pas bloquer les lookups
  internes de la directory faits pour le bridge d'appel (`user/xxx@domain`),
  qui n'ont pas de `sip_via_protocol`.
  Validé par test réel : poste en `tls` → REGISTER en UDP refusé (403 Forbidden),
  REGISTER en TLS accepté (200 OK).
Reste à faire : TLS pour les trunks — bloqué en attente de confirmation ISP
(le fournisseur de lignes SIP doit accepter TLS de son côté).
Fichiers : models/sip.py, api/v1/endpoints/extensions.py, api/v1/endpoints/xml_curl.py,
alembic/versions/0019_extension_transport.py, frontend/src/pages/ExtensionDetail.jsx,
+ config serveur (vars.xml, sip_profiles/internal.xml, conf/tls/*).

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
| TASK-S020.1 | esl ip nat        | IP publique/privée par registration — diagnostic NAT/SIP ALG ✓                       |
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

#### TASK-S020.1 [x] IP publique/privée sur les registrations (diagnostic NAT/SIP ALG)
Demande de l'utilisateur : afficher l'IP publique ET l'IP privée de chaque poste
enregistré côté ERPCRM (fiche compagnie), comme dans ScopServ — sert à diagnostiquer
si le SIP ALG est actif ou s'il y a un double NAT chez le client (les deux IP
identiques = ALG actif ou double NAT).
Fait :
- `_parse_registrations(raw)` dans `esl.py` : parse `show registrations as json`,
  extrait `network_ip` (IP publique réelle vue par FreeSWITCH, fiable) et l'IP dans
  le champ `url` du Contact SIP via regex `@([0-9a-fA-F:.]+):` (IP annoncée par le
  poste lui-même, souvent l'IP LAN).
- `RegistrationOut` : ajout `public_ip`, `private_ip`, `port`.
- `tenant_registrations()` réécrit pour appeler `show_registrations()` une seule fois
  pour tout le tenant (au lieu d'un appel `sofia_contact()` par extension) puis
  matcher par username — plus rapide, moins d'appels ESL.
Fichiers : backend/app/api/v1/endpoints/esl.py.
Consommé côté ERPCRM par TASK-023.1 (voir TASKERPCRM.md).

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

#### TASK-S022 [~] Lien extension ↔ contact ERPCRM
Correction sur la doc précédente : `ERPCRM_API_KEY` dans sipv/.env est la clé que SIPV
VALIDE quand ERPCRM l'appelle (direction ERPCRM→SIPV, /sync/company). La clé que SIPV
PRÉSENTE à ERPCRM (direction SIPV→ERPCRM) est `SIPV_API_KEY` — deux clés distinctes,
une par sens, ajoutée à config.py + .env des deux côtés (2026-07-18).

Fait :
- Migration `0018_extension_erpcrm_contact_id` : `erpcrm_contact_id` (UUID nullable, pas
  de FK cross-DB — ERPCRM et SIPV ont des bases séparées) sur sip_extensions
- `core/erpcrm_client.py` (nouveau) : client httpx — search_contact (GET ?search=),
  create_contact (POST), update_contact (PUT), tous avec header X-Api-Key: SIPV_API_KEY
- `extensions.py` : `_link_erpcrm_contact()` appelée après création d'une extension —
  cherche par nom, lie si trouvé (PUT sipv_sync=true + extension), crée sinon (POST).
  Best-effort : si ERPCRM injoignable, l'extension est quand même créée, juste sans lien
  (logué en warning, pas d'exception qui bloque la création du poste)
- `delete_extension` : si erpcrm_contact_id existait, PUT sipv_sync=false sur ERPCRM
  (best-effort, même logique)
- `sync.py` : nouvel endpoint POST /api/v1/sync/erpcrm-event (X-Api-Key, symétrique à
  POST /api/v1/sipv/event côté ERPCRM) — action contact_name_changed, cherche les
  SIPExtension par erpcrm_contact_id, met à jour caller_id_name + freeswitch_synced=false
Syntax-check Python OK sur tous les fichiers touchés.
Reste à faire [~] :
- Pas déployé sur le serveur réel (192.168.1.55) — migrations 0015 à 0018 jamais
  appliquées là-bas, donc rien de tout ça n'est fonctionnel en vrai pour l'instant
- ERPCRM ne fait pas l'inverse (rien n'appelle POST /api/v1/sync/erpcrm-event quand un
  contact change de nom côté ERPCRM — pas fait, pas demandé explicitement ici)
- Pas de test end-to-end réel (nécessite les deux serveurs up avec les clés configurées)
Dépend de : TASK-S037 ✓, TASKERPCRM TASK-018 ✓.
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
| TASK-S018.3 | ux extension  | Identification/site, plan d'appel, renvois, DND, codec liste ordonnée, groupes ✓|

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
- Lien ERPCRM (contact lié, sync nom) : TASK-S022 codée (2026-07-18) mais pas déployée —
  section UI de ExtensionDetail.jsx toujours marquée "à venir", pas encore câblée sur
  erpcrm_contact_id (fait dans une session séparée, pas cette page).
- DND / appels en cours en direct : pas juste un champ, nécessite de nouvelles méthodes
  ESLClient (ex: `show channels`) — plus gros que l'ajout d'un champ, pas fait ici.
- Voicemail et Provisioning restent en lecture seule sur cette page (édition déjà possible
  via VoicemailPage.jsx / ProvisioningPage.jsx) — pas dupliqué le formulaire.
Build frontend vérifié (`npm run build` OK) après chaque ajout, syntax-check Python OK.
Dépend de : TASK-S020 (statut live ESL) ✓, TASK-S016 (schedules, réutilisé) ✓.

#### TASK-S018.3 [x] Identification/site, plan d'appel, renvois, DND, codec liste ordonnée, groupes
Champs ajoutés sur SIPExtension (migration `0020_extension_s018_3` -- appliquée sur SIPV,
backend synchronisé et redémarré, testé en direct) :
- `site`, `description` (texte libre)
- `call_permission` (local/national/international, défaut "international" = comportement
  actuel préservé). ⚠️ PAS ENCORE APPLIQUÉ par le dialplan — `OutboundRoute` n'a aucun
  concept de palier d'appel, `_handle_dialplan` ne vérifie rien. Le champ est stocké,
  visible/éditable sur la fiche, et reflété dans `toll_allow` du XML directory (comme
  avant, mais dynamique au lieu d'être codé en dur) — mais rien n'empêche réellement un
  poste "local seulement" de composer à l'international aujourd'hui. Vraie application =
  tâche séparée (toucher `OutboundRoute` + `_handle_dialplan`), pas faite ici pour ne pas
  présenter une fausse sécurité.
- `forward_immediate_enabled/destination`, `forward_busy_enabled/destination`,
  `forward_no_answer_enabled/destination/delay_seconds`, `forward_offline_destination`,
  `dnd_enabled`, `dnd_locked`, `auto_answer_enabled` — ⚠️ MÊME AVERTISSEMENT : champs de
  configuration stockés et éditables, mais AUCUNE action réelle sur les appels (pas
  d'application dans le dialplan). Un déjà existant exemple similaire dans ce fichier :
  "DND / appels en cours en direct... pas fait ici" (note TASK-S018 plus haut) — cohérent
  avec cet avertissement, pas nouveau comme lacune.
- `max_concurrent_calls`, `distinctive_ring`, `record_mode` (manual/auto).
- `codec_list` (remplace `codec`) : liste ordonnée, défaut `ulaw,alaw,g722,g729` (PCMU en
  tête, décision projet 2026-07-23 -- meilleur rapport qualité/poids). CELUI-LÀ EST
  RÉELLEMENT APPLIQUÉ : `xml_curl.py::_user_xml()` construit `absolute_codec_string` à
  partir de la liste complète (dans l'ordre), vérifié en direct sur l'extension t1001-100
  après redémarrage : `absolute_codec_string=PCMU,PCMA,G722,G729`. Avant ce changement,
  cette variable n'était JAMAIS émise (codec était toujours null) — FreeSWITCH utilisait
  ses propres défauts de profil sans contrôle ; c'est un vrai changement de comportement
  (positif, voulu), pas juste un champ décoratif.
- `max_contacts` : défaut Python changé 3→1 pour les NOUVELLES extensions seulement — pas
  de backfill sur les extensions existantes (déjà à 3, laissées telles quelles pour ne
  pas risquer de casser un poste multi-appareils déjà configuré).
- Groupes d'appartenance (IVR/queue/ring group) : PAS un champ stocké — calculé à la volée
  dans `GET /extensions/{id}` (`_groups_for()`, jointures Queue/QueueMember + scan
  RingGroup.members) donc toujours à jour, pas de désync possible. Volontairement absent
  du endpoint de LISTE (`GET /extensions/tenant/{id}`) pour éviter du N+1 sur une page qui
  liste potentiellement beaucoup de postes — seulement sur la fiche unitaire.

Fichiers touchés : `backend/app/models/sip.py`, `backend/app/api/v1/endpoints/extensions.py`,
`backend/app/api/v1/endpoints/xml_curl.py` (codec_list + toll_allow dynamique),
`backend/alembic/versions/0020_extension_s018_3_fields.py`,
`frontend/src/pages/ExtensionDetail.jsx` (3 nouvelles sections : Identification & plan
d'appel, Renvois & DND, Groupes d'appartenance -- lecture seule).

⚠️ Rappel architecture (découvert cette session) : le code qui tourne réellement est sur
LE SERVEUR SIPV lui-même (`/home/sipv/sipv/backend`), PAS la copie locale
`/home/simpleip/sipv/backend` sur ce serveur ERPCRM (les deux ne sont PAS le même
répertoire malgré des chemins qui se ressemblent) — synchronisation faite par `rsync`
manuel des 4 fichiers backend touchés, PUIS `alembic upgrade head` exécuté sur SIPV, PUIS
`systemctl restart sipv-backend`. Le frontend SIPV n'a PAS de service actif du tout en ce
moment (nginx ne sert que l'ancien FusionPBX abandonné) — `ExtensionDetail.jsx` est
synchronisé en code source mais rien à redémarrer/vérifier en live côté UI pour l'instant.

Testé en direct après déploiement : migration appliquée + backfill correct (`codec` NULL
existant → `codec_list` complet par défaut, pas de perte de config) ; `GET`/`PUT`
extension avec les nouveaux champs ; XML directory (`/xml_curl` section=directory) confirmé
avec `absolute_codec_string` et `toll_allow` corrects ; les 2 postes de test toujours
`Registered(TLS)` sans interruption après le redémarrage du service.

Reste à faire (hors scope volontaire de cette tâche, à faire séparément et consciemment) :
1. Application réelle du plan d'appel (OutboundRoute + _handle_dialplan).
2. Application réelle des renvois/DND/réponse automatique (actions dialplan).
3. UI : widget de réordonnancement des codecs plus convivial (actuellement un champ texte
   CSV) -- fonctionnel, pas raffiné.

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

#### TASK-S027 [x] Permissions téléphoniques PortalUser ERPCRM
Fait côté ERPCRM (voir TASKERPCRM.md TASK-017 pour le détail complet) — les 13 champs
boolean existent sur portal_users, avec UI Admin.jsx pour les cocher par accès portail.
⚠️ Validation serveur systématique pas encore applicable : SIPV n'a aucun endpoint qui
consomme ces permissions pour l'instant, puisque TASK-S028/S029 (qui liraient ces
permissions avant d'exposer des données) ne sont pas commencées. La règle "le backend SIPV
doit toujours revalider, jamais faire confiance à l'UI seule" reste à appliquer quand
S028/S029 seront codées.
Fichier modifié : /home/simpleip/erpcrm/backend/app/models/portal.py (+ portal.py endpoints,
+ migration, + Admin.jsx — hors du repo SIPV, voir TASKERPCRM.md).

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

#### TASK-S036 [~] POC bout en bout — premier jalon
Valide que l'architecture complète fonctionne de bout en bout.
Voir détail complet dans "Points critiques" en haut du fichier (2026-07-18).
Étapes dans l'ordre :
1. Créer compagnie ERPCRM → déclenche création tenant SIPV automatique (sync/company) — ✓ fait manuellement (checkbox ERPCRM TASK-022), pas testé via le vrai flux checkbox UI (fait par curl direct)
2. Créer contact ERPCRM + cocher sipv_sync → vérifier lien dans SIPV — non testé dans ce sens (ERPCRM→SIPV) cette session
3. Créer extension depuis SIPV → vérifier contact ERPCRM mis à jour — ✓ confirmé involontairement : la création des extensions 100/101 a bien déclenché la création automatique des contacts "Test Un"/"Test Deux" dans ERPCRM (TASK-S022 fonctionne)
4. Commit changements → vérifier que mod_xml_curl sert directory.xml correct pour ce tenant — ✓ confirmé
5. Enregistrer softphone avec credentials extension → vérifier "Registered" — ✓ confirmé (baresip, 200 OK, visible dans sofia status reg)
6. Appel interne entre deux extensions du même tenant → vérifier CDR créé en DB — ✓ CONFIRMÉ (RTP établi + CDR créé, voir détail dans "Points critiques")
7. Vérifier isolation : extension tenant A ne peut pas joindre extension tenant B — ✓ confirmé (tenant test t9999 temporaire + extension 200, injoignable en composant "200" depuis t1001 → 486 Busy Here, comme attendu ; tenant/extension/contact de test supprimés après verification)
8. Appel entrant sur DID → IVR → extension → vérifier CDR + routage correct — non testé (explicitement reporté par l'utilisateur — trunk/appels externes = plus tard)
9. Portail ERPCRM "Mon poste" → statut live affiché, CDR personnel visible selon permissions — non fait (TASK-019 ERPCRM pas codée)
10. Alerte : interrompre connexion FreeSWITCH → vérifier alerte reçue — non fait (TASK-S034 pas codée)
Dépend de : TASK-S017.1, TASK-S020, TASK-S021, TASK-S022, TASK-S027, TASK-S028, TASK-S037.
Reste à faire pour clore complètement cette tâche : étapes 8, 9, 10 ci-dessus (8 = explicitement reporté par l'utilisateur, 9/10 = fonctionnalités pas encore codées).

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

---

## Backlog — Configuration complète du poste (demande utilisateur 2026-07-23)

Demande brute très large (fiche poste complète, style UCM/config avancée) — décomposée en
sous-tâches par module existant, `[ ]` toutes, aucune commencée. Champs listés ici =
déjà autorisés le jour où on les code (pas besoin de reconfirmer un par un, voir
CLAUDE.md ERPCRM feedback équivalent côté SIPV : un champ nommé dans une tâche = déjà
une demande). Reste à trancher avant de commencer : **quel module en premier**, et la
question d'architecture transverse ci-dessous (mécanisme d'héritage de settings).

### ✓ Décision transverse tranchée (2026-07-23) — mécanisme d'héritage de settings
Chaîne Poste → Profil de poste (ExtensionProfile, pas encore créé) → Compagnie (Tenant)
→ Global, avec override explicite à chaque niveau (colonne nullable = hérite du parent).
Construit UNE FOIS comme utilitaire réutilisable plutôt que refait à chaque module.

Implémenté maintenant : `sipv/backend/app/core/settings_resolver.py::resolve_setting()`
— fonction générique qui prend un nom de champ + la liste ordonnée des niveaux (objets
ORM, du plus spécifique au plus général) et retourne la première valeur non-None.

Volontairement PAS fait maintenant : créer les tables `ExtensionProfile` et un
singleton `TelephonySettings` (global) vides, sans aucun champ réel à y mettre — aucun
des modules ci-dessous n'est encore codé, donc il n'y a encore aucun champ concret à
hériter. Créer ces tables aujourd'hui serait de l'infrastructure sans besoin mesurable
(règle LOI 4). Convention pour la suite : la PREMIÈRE tâche qui a besoin d'un réglage à
plusieurs niveaux (probablement TASK-S008.2, voicemail "conserver sur le serveur") crée
`ExtensionProfile` et `TelephonySettings` avec ses propres champs, en appelant
`resolve_setting()` — les tâches suivantes ajoutent leurs colonnes aux tables déjà
créées au lieu d'en recréer.

### Ordre d'exécution confirmé par l'utilisateur (2026-07-23)
1. Mécanisme d'héritage (fait, voir ci-dessus)
2. TASK-S039 — Kamailio + rtpengine (SBC, NAT, TLS, sécurité périmètre)
3. Le reste, dans l'ordre des dépendances réelles (chaque tâche liste son "Dépend de")

### TASK-S039 [~] Installation Kamailio + rtpengine (SBC, NAT, TLS, sécurité périmètre)
⚠️ Correction de numérotation : cette tâche était référencée sous "SIPV-T-005" dans
/home/simpleip/TASKS.md (checkpoint de session, namespace différent de celui-ci) — pas
de doublon avec TASK-S005 de ce fichier (DIDs, déjà complété). Utiliser TASK-S039 dans
TASKSIPV.md à partir de maintenant.
Dépend de : rien techniquement, mais logiquement avant TASK-S014.2 (affichage IP
publique/statut F2B fiable pour un poste distant derrière NAT).
Fichiers cibles : nouveaux fichiers de config Kamailio (kamailio.cfg) + rtpengine
(rtpengine.conf) sur 192.168.1.55, service systemd pour chacun, règles pare-feu/NAT,
intégration avec les profils sofia FreeSWITCH existants (sipv-internal).

⚠️ Important — S039 ne résout PAS le blocage d'accès distant connu ([[project_sipv_remote_access_blocker]]
en mémoire) : ce blocage est causé par le routeur qui ne redirige aucun port vers le
serveur (zéro paquet n'arrive, confirmé par tcpdump le 2026-07-18), en amont du serveur
SIPV lui-même. Kamailio/rtpengine ne changent rien à ça — utile quand même pour le
périmètre de sécurité local et pour TASK-S014.2, mais ne pas présenter ça comme "accès
distant réparé" une fois fait.

Audit fait le 2026-07-23 (SSH rétabli, voir TASKS.md) :
- Ubuntu 26.04. `kamailio` (6.0.5-1ubuntu1) et `rtpengine` (13.5.1.4-1) disponibles direct
  via apt (universe Ubuntu) — pas besoin de dépôt tiers ni de compiler depuis les sources.
- sudo sans mot de passe disponible pour l'utilisateur `sipv`.
- Aucune IP publique directement sur l'hôte (seulement 192.168.1.55 LAN + loopback) ;
  IP publique 142.112.42.52 vue seulement en sortant (NAT sortant du routeur) — cohérent
  avec le blocage connu.
- Aucune règle NAT configurée actuellement (`iptables -t nat -L` = policies ACCEPT vides).
- FreeSWITCH écoute actuellement DIRECTEMENT sur 192.168.1.55:5060/5061/5066/5080
  (profils internal + external) — c'est le trafic live que Kamailio devrait éventuellement
  prendre en façade. Ne pas rebrancher les ports sans un cutover supervisé (voir plus bas).
- Processus `baresip` de test (POC TASK-S036) encore en cours d'exécution en arrière-plan
  sur le serveur — bruit inoffensif, pas touché.
- [x] 13:38 UTC : première tentative bloquée par `apt.systemd.daily` qui tenait le lock
  dpkg. ⚠️ Piège rencontré : `pgrep -f apt.systemd.daily` a donné un faux positif
  "STILL_RUNNING" à répétition — la commande de vérification matchait SA PROPRE ligne de
  commande (le pattern cherché apparaît dans l'argument passé à `pgrep -f`). Vérifié
  correctement via `sudo fuser /var/lib/dpkg/lock-frontend` (rien = lock libre). Ne pas
  refaire ce piège : pour vérifier un processus par nom avec pgrep -f depuis une commande
  qui contient elle-même ce nom, utiliser `pgrep -f '[a]pt.systemd.daily'` (astuce
  bracket) ou vérifier directement la ressource (lock file, port) plutôt que le nom de
  process.
- [x] 13:54 UTC : `apt-get install -y kamailio kamailio-tls-modules rtpengine` réussi.
  Inclut `rtpengine-kernel-dkms` (module noyau construit + signé avec succès pour les
  deux noyaux installés, 7.0.0-27-generic et 7.0.0-28-generic — Secure Boot désactivé,
  clé MOK auto-générée). Services créés : `kamailio.service`, `rtpengine-daemon.service`
  (actif par défaut, écoute déjà `127.0.0.1:2223` en ng-protocol — local seulement, aucun
  port RTP/SIP public touché), `rtpengine-recording-daemon.service`.
- [x] `kamailio.service` a échoué au premier démarrage (`Result: exit-code`, 5 tentatives
  puis rate-limité par systemd — pas un crash-loop actif, juste resté "failed"). Cause
  réelle : le kamailio.cfg vendor par défaut (1108 lignes, template standard Debian/
  Ubuntu) a une ligne `listen=` commentée par défaut → kamailio bind sur port 5060 TOUTES
  IPs par défaut → collision avec FreeSWITCH qui a déjà ce port. Pas un bug de contenu.
- [x] Fix : `/etc/kamailio/kamailio-local.cfg` créé (le fichier vendor a son propre hook
  d'override `import_file "kamailio-local.cfg"` — ne pas éditer le fichier vendor
  directement) avec seulement `listen=udp:192.168.1.55:5090` + `listen=tcp:...:5090`
  (port de test, PAS 5060/5061/5066). Validé avec `kamailio -c -f kamailio.cfg` (syntax
  check officiel) avant de démarrer. `systemctl reset-failed kamailio` puis `start` →
  actif, écoute UDP+TCP sur :5090 uniquement. FreeSWITCH reconfirmé intact sur
  5060/5061/5066/5080/7443/8021 après coup.

[x] 14:10-14:20 UTC : logique de routage écrite et validée.
- `/etc/kamailio/kamailio.cfg` REMPLACÉ par une config custom minimale (vendor original
  sauvegardé intact dans `/etc/kamailio/kamailio.cfg.vendor-orig`, ne jamais l'écraser) --
  le template vendor (1108 lignes) est conçu pour un Kamailio registrar/proxy autonome
  avec DB (usrloc/MySQL), pas pour notre rôle visé (proxy NAT-aware en façade qui relaie
  tout vers FreeSWITCH inchangé, qui garde l'auth/registrar via xml_curl multi-tenant).
  Patcher le vendor par flags aurait été plus risqué que d'écrire une config dédiée.
- Modules chargés : sl, tm, rr, maxfwd, textops, siputils, sanity, xlog, ctl, cfgutils,
  kex, corex, tmx, counters, pv, nathelper, rtpengine (PAS usrloc/registrar -- volontaire).
  `modparam("rtpengine","rtpengine_sock","udp:127.0.0.1:2223")` -- pointe vers le
  rtpengine déjà actif (rtpengine-daemon.service).
  `modparam("rr","enable_full_lr",1)`.
- request_route : maxfwd -> sanity_check -> force_rport/nat_uac_test/fix_nated_contact
  (NAT) -> si in-dialog (has_totag) : loose_route + rtpengine_manage() sur BYE/CANCEL/
  INVITE-UPDATE-ACK avec SDP, sinon 404 -- si nouvelle requête : record_route() +
  rtpengine_manage() si SDP + `$du = "sip:192.168.1.55:5060"` (destination FIXE =
  FreeSWITCH profil internal, inchangé) -> route[RELAY] (t_relay()).
  onreply_route : rtpengine_manage() sur les réponses 1xx/2xx avec SDP.
  Toujours sur le port de TEST 5090 (udp+tcp) -- 5060/5061/5066 intouchés, reconfirmé
  après coup.
- Validation faite avec `sipsak` (déjà installé sur le serveur) :
  - `sipsak -U -s sip:<user>@t1001 -a '<pass>' -H 192.168.1.55 -r <port> -v`
    (`-H`/`-r` = destination transport réelle, indépendante du domaine dans l'URI --
    nécessaire ici puisque "t1001" n'est pas un nom DNS résoluble ; ajout temporaire
    `192.168.1.55 t1001` dans /etc/hosts pour que `sipsak` accepte de résoudre l'URI,
    RETIRÉ après coup -- c'était pour l'outil de test seulement, Kamailio lui-même
    n'en a jamais eu besoin, `$du` est câblé en dur).
  - Test 1 (t1001-102, "Test Trois") : 403 Forbidden identique en direct (port 5060)
    ET via Kamailio (port 5090) -- confirmé PAS causé par le relais (contrôle négatif).
    Cause réelle probable : le profil internal impose TLS (voir
    [[project_sipv_remote_access_blocker]]), REGISTER en UDP simple rejeté par
    politique, peu importe le chemin. Hors scope S039, état pré-existant de cette
    extension de test, pas touché.
  - Test 2 (t1001-100, extension ACTUELLEMENT enregistrée en direct via TLS/baresip) :
    même résultat identique en direct et via Kamailio (403, même raison que ci-dessus,
    UDP simple). **Preuve de transparence byte-for-byte du relais** : comportement
    strictement identique des deux côtés pour deux comptes différents = la logique de
    routage ne modifie rien au comportement de FreeSWITCH, elle relaie fidèlement.
  - Test avec succès `200 OK` bout en bout PAS encore fait -- nécessiterait soit un
    listener TLS côté Kamailio (terminaison TLS, gestion de certificat -- pas encore
    configuré), soit un profil de test acceptant l'UDP simple. Ne PAS affaiblir la
    politique TLS de FreeSWITCH juste pour obtenir un test plus "propre" -- attendre
    soit la config TLS de Kamailio (prochaine étape naturelle), soit une décision
    explicite de l'utilisateur.

[x] 2026-07-23 21:1x UTC — Listener TLS sur Kamailio fait et validé avec un vrai
`200 OK` bout en bout (session interactive, utilisateur de retour, autorisation
explicite : "le serveur n'est pas en ligne pour des clients, on peut faire des
cutover").

⚠️ Trouvaille architecture avant de coder : relayer en TLS-vers-clair (déchiffrer chez
Kamailio, relayer en UDP/TCP vers FreeSWITCH) aurait cassé la vérification
`sip_via_protocol` déjà en place dans `xml_curl.py` (compare le transport vu par
FreeSWITCH au `transport` configuré par poste) — TOUS les postes TLS auraient
silencieusement échoué leur authentification après le cutover. Solution : TLS de
bout en bout (client → Kamailio → FreeSWITCH, jamais de terminaison en clair) —
FreeSWITCH voit exactement ce qu'il voit aujourd'hui, aucune modification de la
logique de vérification existante nécessaire.

Implémenté : `/etc/kamailio/tls.cfg` (réutilise le certificat FreeSWITCH existant —
`/usr/local/freeswitch/conf/tls/agent.pem` + `cafile.pem`, aucun nouveau certificat,
aucun nouveau trust côté clients), `enable_tls=1` + `loadmodule "tls.so"` +
`listen=tls:192.168.1.55:5091` (port de test) dans kamailio.cfg, `$du` pointe vers
`sip:192.168.1.55:5061;transport=tls` (le port TLS réel de FreeSWITCH, pas 5060).

Validé avec un VRAI client (pas sipsak — sipsak a échoué sur ce test avec une erreur
de connexion TCP au moment de relayer la réponse 401→REGISTER-avec-auth, cause pas
identifiée avec certitude, possiblement une limitation de sipsak sur les transactions
TLS/TCP à plusieurs échanges plutôt qu'un vrai bug Kamailio — pas creusé plus loin
puisqu'un test avec un client réel a directement confirmé que ça marche) : instance
`baresip` temporaire pointée sur `192.168.1.55:5091;transport=tls` au lieu du port
FreeSWITCH direct, avec les vrais identifiants de t1001-100. Résultat :
`200 OK ... [1 binding]`. Confirmé aussi côté FreeSWITCH (`show registrations`).

⚠️ Incident pendant le test (résolu, aucun impact durable) : le test bare­sip utilisait
le même compte (t1001-100) que l'instance de test déjà enregistrée en direct — le
nouvel enregistrement via Kamailio a remplacé l'ancien (pas ajouté, malgré
`max_contacts=3` sur cette extension) plutôt que de coexister. En tuant le client de
test, t1001-100 s'est retrouvé complètement désenregistré. Cause d'un délai de plus :
`nohup ... &` depuis une commande SSH one-shot ne garantit PAS la survie du process
après la fin de la session SSH sur ce serveur (`loginctl show-user sipv` confirme
`Linger=no`) — un premier essai de relance via nohup a semblé échouer (code 255) mais
a en fait survécu en silence, créant un DOUBLON quand j'ai relancé une deuxième fois
via `systemd-run --uid=sipv --unit=...` (méthode fiable, à utiliser desormais pour
tout process de test qui doit survivre à la session SSH sur ce serveur). Doublon
détecté et nettoyé, état final confirmé propre (exactement 2 process, 2
enregistrements, les 2 corrects).

### Tentative de cutover réel (2026-07-23 22h, autorisée par l'utilisateur) — ROLLBACK
Fait : `internal.xml` modifié (`sip-ip=127.0.0.1`, `rtp-ip` inchangé — media reste
direct, ws-binding/wss-binding pinnés sur l'IP LAN explicitement), Kamailio basculé
sur les vrais ports 5060 (udp/tcp) + 5061 (tls), `$du` pointé vers
`127.0.0.1:5061;transport=tls`. `rtpengine_manage()` désactivé volontairement pour ce
premier cutover (jamais validé avec un vrai appel/audio, pas mis dans le chemin
critique d'un cutover live avant test séparé).

Résultat immédiat : les 2 enregistrements TLS existants ont basculé tout seuls, de
façon transparente, sans intervention — bon signe. MAIS un appel test
(`originate user/t1001-101@t1001 &echo`) a échoué instantanément en `503`, alors
qu'il n'échouait jamais aussi vite avant.

⚠️ Cause identifiée : FreeSWITCH route un appel VERS un poste enregistré en envoyant
une NOUVELLE requête directement au Contact annoncé par le poste au moment de son
REGISTER — pas via la connexion existante. Avant le cutover, ce Contact pointait
directement vers FreeSWITCH (relation directe). Après le cutover, ce Contact pointe
toujours vers le poste lui-même, mais FreeSWITCH (maintenant sur loopback) n'a plus
de chemin pour transmettre cet appel EN PASSANT PAR Kamailio — il tente une connexion
directe et échoue. Fix correct pour une vraie prod : Kamailio doit insérer un header
`Path` (RFC 3327, module `path.so` déjà disponible dans `kamailio-tls-modules` — bien
que le nom du paquet suggère juste TLS, à vérifier) au moment du REGISTER, et
FreeSWITCH doit honorer ce Path pour renvoyer les appels sortants-vers-poste via
Kamailio plutôt que directement au Contact. PAS fait dans cette session — rollback
immédiat plutôt que de laisser un système qui "semble" marcher (s'enregistre) mais ne
peut plus recevoir d'appels, ce qui aurait été pire que l'état d'avant.

Rollback exécuté et vérifié : `internal.xml` restauré depuis
`internal.xml.backup_20260723_cutover`, Kamailio remis sur les ports de test
(5090/5091), les 2 postes de test re-enregistrés tout seuls après coup.

⚠️ Découverte séparée, IMPORTANTE, PAS liée au cutover (confirmée présente même dans
l'état pleinement restauré, donc préexistante à toute cette session) : le même test
d'appel (`originate user/t1001-101@t1001 &echo`) échoue AUSSI en direct (sans
Kamailio du tout), avec un symptôme différent (timeout, pas 503 instantané). Le log
de `baresip101` montre `tls: accept error: (r=-1, ssl_err=1)` exactement au moment de
la tentative -- FreeSWITCH essaie d'ouvrir une NOUVELLE connexion TLS sortante vers
le poste pour lui livrer l'appel, et cette connexion échoue au handshake TLS côté
poste. Ni testé ni corrigé ici (hors scope de cette investigation cutover) mais
potentiellement significatif : si ce mécanisme ne marche jamais pour un appel
entrant-vers-poste via une NOUVELLE connexion TLS, ça pourrait expliquer pourquoi
seul le flux "poste appelle activement" a été validé dans le POC TASK-S036 (l'appelant
utilise sa propre connexion existante, pas de nouvelle connexion TLS entrante requise)
et pas le flux inverse. À investiguer séparément, avec l'utilisateur si besoin d'un
vrai téléphone (pas juste baresip) pour confirmer si c'est spécifique à baresip ou
plus général.

### ✓ Mécanisme Path résolu (2026-07-23 22h30, sur le port de test avant nouveau cutover)
FreeSWITCH honore nativement le header `Path` (RFC 3327) — confirmé dans le code source
(`sofia_reg.c` ligne ~1523, `sip->sip_path` → stocké comme `fs_path` sur la
registration). Rien à activer côté FreeSWITCH.

Côté Kamailio : `loadmodule "path.so"` (déjà présent sur disque, aucun paquet
supplémentaire), `modparam("path", "use_received", 1)`, et sur `REGISTER`
spécifiquement (avant `record_route()`/`rtpengine`, qui ne s'appliquent pas à
REGISTER) : `add_path();` puis relais normal.

Testé sur le port TLS de test (5091) avec un vrai client `baresip` (t1001-100) :
- `sofia status profile internal reg` confirme `fs_path=...192.168.1.55:5091;
  transport=tls` correctement enregistré sur la registration.
- `originate user/t1001-100@t1001 &echo` : **le 503 instantané a disparu**. L'appel
  atteint maintenant `CS_CONSUME_MEDIA` (routage correct via Kamailio) et échoue
  seulement au bout du timeout normal (408), exactement comme un appel direct sans
  Kamailio échoue pour la raison ci-dessous — donc le problème spécifique au cutover
  (absence de chemin de retour) est réglé. Confirmé aussi côté logs Kamailio (retransmissions
  normales, pas de rejet immédiat).

Nettoyage fait : client de test arrêté, les 2 postes de test remis à `Registered`/
`Reachable` (un `systemctl restart` sur l'unité systemd du poste 100 a laissé un
process orphelin une fois de plus — tué manuellement, état final vérifié propre).

### ✓ Bug TLS pré-existant — résolu, cause réelle identifiée (2026-07-23 22h40)
Root cause trouvée et confirmée, PAS un bug FreeSWITCH ni Kamailio : les deux comptes
de test `baresip` (`.baresip100`, `.baresip101`) n'avaient AUCUN certificat TLS
configuré (`sip_certificate` commenté dans leur `config`, aucun fichier `cert.pem`
présent). Quand FreeSWITCH ouvre une nouvelle connexion TLS sortante pour livrer un
appel entrant vers le contact enregistré, `baresip` doit agir comme SERVEUR TLS
(accepter le handshake) — sans certificat à présenter, le handshake échoue
immédiatement (`tls: accept error: (r=-1, ssl_err=1)`, `SSL_ERROR_SSL`). Ce n'était
donc qu'une lacune de configuration des clients de test, pas un défaut de
l'infrastructure.

Validation : génération d'un certificat auto-signé pour chaque compte
(`openssl req -x509 ...`), ajout de `sip_certificate /home/sipv/.baresipXXX/cert.pem`
(chemin ABSOLU requis — le chemin relatif `cert.pem` seul ne fonctionne pas, testé et
confirmé), redémarrage propre des deux clients. Nouveau test `originate
user/t1001-100@t1001 &echo` (sans Kamailio, direct) : plus aucune erreur TLS, le canal
atteint `180 Ringing` (`Ring-Ready`) — la connexion TLS entrante est acceptée
correctement. Le `NO_ANSWER` après 60s est normal et attendu : `baresip` ne
répond pas automatiquement aux appels entrants sans script dédié, ce n'est pas un
échec de livraison.

**Conclusion** : aucune correction nécessaire côté Kamailio ni FreeSWITCH. RFC 5626
"SIP Outbound" n'est pas nécessaire pour ce problème (piste explorée puis écartée
une fois la vraie cause confirmée) — à garder en tête plus tard uniquement si de
vrais téléphones derrière un NAT strict n'arrivent pas à accepter de connexions TLS
entrantes (les Grandstream GXP2135 génèrent normalement leur propre certificat et
acceptent le TLS entrant nativement, donc ce cas ne devrait pas se reproduire avec du
matériel réel correctement provisionné — à confirmer quand un vrai téléphone sera
disponible).

### ✓ CUTOVER LIVE réussi (2026-07-23 22h50, tentative 2)
Autorisé explicitement par l'utilisateur ("oui fait l'etape reel faire ecouter
kamailo", serveur pas encore en production client). Kamailio écoute maintenant sur
les VRAIS ports 5060 (UDP/TCP) et 5061 (TLS) sur l'IP LAN 192.168.1.55. FreeSWITCH
profil `internal` déplacé sur loopback (`sip-ip=127.0.0.1`), `ws-binding`/
`wss-binding` pinnés explicitement sur l'IP LAN (5066/7443, non affectés). RTP
(media) toujours en direct téléphone↔FreeSWITCH, non proxié par rtpengine pour ce
premier cutover (`rtpengine_manage()` resté désactivé, jamais validé avec audio réel
dans cette session).

Deux bugs de routage supplémentaires trouvés et corrigés PENDANT cette tentative
(absents du test sur port 5090/5091 parce que ce test ne couvrait que la direction
client→FreeSWITCH, jamais FreeSWITCH→client) :

1. **`loose_route()` gaté derrière `has_totag()`** : ne s'évaluait jamais pour une
   requête initiale (pas encore de to-tag) même routée via nous. Corrigé en évaluant
   `loose_route()` de façon inconditionnelle, avant `has_totag()`.
2. **`fs_path` n'insère PAS un header Route SIP** : contrairement à l'hypothèse
   initiale, `sofia_glue.c` utilise le Path reçu comme "proxy route" (outbound
   proxy, au sens next-hop) plutôt que comme un header `Route` standard — donc
   `loose_route()` ne matche jamais les requêtes FreeSWITCH→client, même après le
   fix #1. Conséquence observée : Kamailio réappliquait `$du = FreeSWITCH` sur ces
   requêtes et se les renvoyait à lui-même en boucle (404/NO_ROUTE_DESTINATION
   immédiat côté FreeSWITCH, qui recevait un INVITE avec un R-URI qu'il ne savait
   pas router). Corrigé en distinguant la direction par IP source (`$si ==
   "127.0.0.1"` = requête sortante de FreeSWITCH, où le R-URI contient déjà le
   vrai contact du client → ne pas écraser `$du`, relayer tel quel).

Validation post-fix : `originate user/t1001-101@t1001 &echo` (poste TLS, Path,
via Kamailio sur ports live) → `Ring-Ready` atteint proprement, aucune boucle,
aucun 404/503. Les deux comptes de test restent `Registered(TLS)`/`Reachable`
après le cutover. `NO_ANSWER` final normal (le client de test `baresip`
n'automatise pas la réponse dans ce contexte headless malgré `answermode=auto` --
limite du client de test, pas un défaut d'infrastructure). Validation complète
avec audio réel (`200 OK`, RTP bidirectionnel) **pas encore faite** -- nécessite un
vrai téléphone ou un client scriptable capable de répondre automatiquement ; à
faire dès qu'un téléphone physique est disponible (photo GXP2135 déjà reçue pour
TASK-S011.3).

Config live actuelle : `/etc/kamailio/kamailio.cfg` sur 192.168.1.55 (backups
successifs conservés : `kamailio.cfg.testport_path_backup_20260723`,
`/tmp/kamailio_broken_routing_backup.cfg` pour la version avec le bug #2 non
corrigé). `internal.xml` toujours sauvegardé en
`internal.xml.backup_20260723_cutover` (état pré-cutover) si rollback nécessaire.

Pause volontaire ici pour enchaîner sur TASK-S018.3 (rien dans le backlog restant ne
dépend de S039 sauf S014.2). Reste explicitement hors scope de cette session : audio
réel avec vrai téléphone, réactivation de rtpengine (jamais testée), et
`max_contacts` (premier-branché-gagne) demandé par l'utilisateur mais pas encore
implémenté.

### Clarifications de l'utilisateur (2026-07-23)
- **Codecs** : pas un seul codec par défaut — une LISTE ordonnée par meilleur rapport
  qualité/poids (PCMU en tête). S'applique à TASK-S018.3 (remplace le `codec: str|None`
  actuel par une liste ordonnée) et doit probablement vivre au niveau du mécanisme
  d'héritage ci-dessus (liste par défaut au niveau global/compagnie, override par poste).
- **Provisioning et changement d'appareil physique** : la configuration (extension,
  réglages, mapping de boutons) reste attachée au POSTE logique (SIPExtension), pas à
  l'appareil physique. Remplacer un téléphone = mettre à jour `mac_address` et
  `serial_number` sur le même enregistrement `ProvisionedPhone` (pas en créer un
  nouveau), tout le reste (extension_id, config, mapping boutons de TASK-S011.3) ne
  bouge pas. À respecter dans TASK-S011.2/S011.3 : l'UI de remplacement de téléphone
  doit être une action "changer le MAC/SN de cet appareil", pas "supprimer et recréer".

### ✓ TASK-S039.1 [x] Chiffrement mot de passe SIP + TLS inter-serveurs ERPCRM↔SIPV (2026-07-24)
Contexte : demande de voir le mot de passe SIP en clair sur la fiche contact ERPCRM
(TASK-023.2 TASKERPCRM.md) pour configurer un téléphone manuellement quand le
provisioning automatique est bloqué par le réseau du client. Condition posée par
l'utilisateur pour l'exposer : le chiffrer au repos. En le faisant, constat que
l'appel HTTP ERPCRM↔SIPV existant (port 8020/8010, plain HTTP, restreint par
pare-feu à l'IP de l'autre serveur uniquement) allait maintenant transporter ce mot
de passe en clair sur le réseau — l'utilisateur a demandé d'ajouter le TLS entre les
deux serveurs pour fermer ce trou aussi.

**Chiffrement (Fernet)** :
- `app/core/crypto.py` (nouveau, partagé) : `encrypt()`/`decrypt()`, clé dérivée de
  `SECRET_KEY` (même pattern que `provisioning.py` pour `encrypted_admin_password`,
  non touché, juste le même principe réutilisé).
- `SIPExtension.password` chiffré à l'écriture (create/update/regenerate-password
  dans `extensions.py`), déchiffré à la lecture (`xml_curl.py` pour l'auth digest
  FreeSWITCH, nouveau `GET /extensions/{id}/connection-info` pour l'affichage humain).
- Migration `0026_encrypt_extension_passwords` : chiffre en place les 3 mots de passe
  existants (postes 100/101/102). Validé en direct : les 2 postes de test TLS
  (`baresip`) se sont ré-enregistrés avec succès après le redémarrage du service,
  confirmant que l'auth digest FreeSWITCH fonctionne toujours avec le mot de passe
  déchiffré à la volée.
- `GET /extensions/{id}/connection-info` (X-Api-Key) : retourne username, mot de
  passe déchiffré, serveur (`settings.SIPV_HOST`), port (5061 TLS / 5060 UDP-TCP
  selon `ext.transport`), domaine (`Tenant.account_number`). Pas de log d'audit sur
  cette lecture (même choix que `reveal-admin-password`, précédent déjà établi).

**TLS inter-serveurs** : CA privée auto-signée générée localement (jamais transmise
en clair, clé privée de la CA reste uniquement sur ERPCRM dans
`erpcrm/backend/certs/ca.key`), un certificat par serveur (SAN = IP LAN).
- Nouveau port TLS DÉDIÉ sur chaque backend, en plus du port HTTP existant qui reste
  inchangé (sert le frontend, jamais touché) :
  - SIPV : 8022 (8021 initialement prévu mais déjà pris par l'ESL FreeSWITCH —
    changé après conflit détecté au démarrage du service).
  - ERPCRM : 8011.
- Chaque port TLS lancé comme un DEUXIÈME processus uvicorn (nouvelle unité systemd
  `sipv-backend-tls.service` / `erpcrm-backend-tls.service`), même app FastAPI, donc
  mêmes routes/auth X-Api-Key — juste un chemin réseau chiffré en plus.
- Pare-feu : nouveau port restreint à l'IP de l'autre serveur uniquement (SIPV :
  iptables policy DROP par défaut déjà en place, règle ACCEPT ajoutée + persistée
  via `netfilter-persistent` malgré une erreur du plugin ip6tables non liée à notre
  changement, ipv4 confirmé persisté manuellement. ERPCRM : policy ACCEPT par
  défaut sur ce serveur — donc règle ACCEPT explicite pour l'IP de SIPV suivie d'un
  DROP explicite pour tout le reste sur ce port précis, pas de changement à la
  policy globale ; **pas de persistance au reboot configurée côté ERPCRM**
  — `iptables-persistent` n'est pas installé sur cet hôte et n'a pas été ajouté
  (hors scope, changerait le comportement de démarrage du serveur) — la règle sera
  perdue au prochain redémarrage du serveur ERPCRM, à refaire manuellement si ça
  arrive avant qu'une vraie solution de persistance soit mise en place consciemment.
- `SIPV_API_URL`/`ERPCRM_API_URL` pointent maintenant vers `https://...` sur les
  nouveaux ports, `sipv_client.py`/`erpcrm_client.py` vérifient le certificat de
  l'autre serveur contre la CA partagée (`verify=<chemin vers ca.pem>`).
- Piège rencontré : la CA auto-signée générée sans extensions X.509v3
  (`basicConstraints`/`keyUsage`) était rejetée par OpenSSL 3.x (utilisé par le venv
  Python d'ERPCRM) avec `CERTIFICATE_VERIFY_FAILED: CA cert does not include key
  usage extension` — fonctionnait quand même avec `curl` (plus permissif) ce qui a
  presque masqué le problème. Corrigé en régénérant le certificat de la CA (pas la
  clé) avec `basicConstraints=critical,CA:TRUE` et `keyUsage=critical,keyCertSign,
  cRLSign` explicites.
- Validé en direct dans les deux sens (ERPCRM→SIPV via `get_connection_info()`,
  SIPV→ERPCRM via `search_contact()`) puis via un vrai appel HTTP complet identique
  à ce que fait le navigateur (login JWT réel + `GET .../sip-extension/
  connection-info`) — mot de passe du poste 102 (Test Trois) récupéré avec succès
  de bout en bout à travers la chaîne complète.

Reste explicitement hors scope de cette session : persistance du pare-feu côté
ERPCRM au reboot (voir note ci-dessus), rotation/renouvellement de la CA (10 ans de
validité, largement suffisant pour l'instant), mTLS (authentification du CLIENT par
certificat en plus du serveur — pas demandé, X-Api-Key déjà en place pour ça).
Fichiers : sipv/backend/app/core/crypto.py (nouveau),
sipv/backend/app/core/config.py, sipv/backend/app/api/v1/endpoints/extensions.py,
sipv/backend/app/api/v1/endpoints/xml_curl.py, sipv/backend/app/core/erpcrm_client.py,
sipv/backend/alembic/versions/0026_encrypt_extension_passwords.py,
sipv/backend/.env (ERPCRM_API_URL), /etc/systemd/system/sipv-backend-tls.service
(nouveau, sur 192.168.1.55), erpcrm/backend/app/core/config.py,
erpcrm/backend/app/core/sipv_client.py, erpcrm/backend/app/api/v1/endpoints/contacts.py,
erpcrm/backend/.env (SIPV_API_URL), erpcrm/backend/certs/ (nouveau, CA + certs),
sipv/backend/certs/ (nouveau, sur 192.168.1.55), /etc/systemd/system/
erpcrm-backend-tls.service (nouveau).

### ✓ TASK-S039.2 [x] SRTP obligatoire (audio chiffré, pas juste la signalisation) (2026-07-24)
Contexte : l'utilisateur a demandé "TLS & SRTP" après avoir compris que TLS (déjà en
place) protège seulement la signalisation, pas l'audio lui-même — objectif exprimé :
viser le plus haut niveau de sécurité technique possible.

**Root-cause trouvée avant de coder (vérifié contre le code source FreeSWITCH,
`/usr/src/freeswitch-1.10.12`, pas devine)** :
- `require-secure-rtp` (paramètre de profil sofia) est du **code mort** dans cette
  version de FreeSWITCH — il positionne `PFLAG_SECURE` mais rien ne lit jamais ce
  flag ailleurs dans `mod_sofia`. Ne pas utiliser ce paramètre, il ne fait rien.
- Le vrai mécanisme : la variable de canal `rtp_secure_media` (valeurs `optional`/
  `mandatory`/`forbidden`), lue par `switch_core_session_parse_crypto_prefs()` dans
  `switch_core_media.c`. Direction-spécifique (`rtp_secure_media_inbound`/`_outbound`)
  avec repli sur `rtp_secure_media` générique.
- Première tentative : ajouter la variable dans le bloc `<variables>` du user SIP
  généré par `xml_curl.py` (`_user_xml()`). **Ne fonctionne PAS pour les appels
  LIVRÉS À un poste** (direction outbound du point de vue de FreeSWITCH) — seulement
  pour les appels que le poste PLACE lui-même. Confirmé en observant le SDP réel
  envoyé (`m=audio ... RTP/AVP`, aucun `a=crypto`) malgré la variable présente dans
  le directory XML de l'utilisateur appelé.
- Fix réel : `switch_channel_get_variable()` retombe sur les variables GLOBALES
  (`switch_core_get_variable`) si rien trouvé sur le canal — vérifié dans
  `switch_channel.c` (`switch_channel_get_variable_dup`). Donc ajout d'une variable
  globale dans `vars.xml` (`<X-PRE-PROCESS cmd="set" data="rtp_secure_media=
  mandatory"/>`) s'applique à TOUT canal, dans les deux sens, sans dépendre du
  chemin d'appel (dialstring `user/...`, bridge, etc.).
- **vars.xml n'est lu qu'au DÉMARRAGE de FreeSWITCH** (pas par `reloadxml`) — a
  nécessité un redémarrage complet du service `freeswitch` (pas juste un restart de
  profil). Vérifié après coup : le profil `internal` est bien resté sur loopback
  (`127.0.0.1:5060/5061`, config persistée dans `internal.xml`, pas affectée par le
  restart), Kamailio toujours actif, les 2 postes de test re-enregistrés sans
  problème après le restart.

**Validation** : après le fix, un appel test montre `m=audio ... RTP/SAVP` avec 10
suites de chiffrement offertes (`AEAD_AES_256_GCM`, `AES_CM_128_HMAC_SHA1_80`,
etc.) — confirmé dans le SDP réel envoyé par FreeSWITCH. Premier essai avec les
clients de test a échoué (`488`, "no common audio codecs — rejected" côté baresip)
— **pas un bug d'infrastructure** : le module `srtp.so` de baresip était chargé mais
le compte n'avait pas `mediaenc=srtp-mand` dans son URI de compte, donc il
n'utilisait jamais SRTP même si disponible. Ajouté `;mediaenc=srtp-mand` aux deux
comptes de test — nouvel essai : offre SRTP acceptée, `Ring-Ready` atteint proprement
(même étalon de validation que le reste de cette tâche — le `NO_ANSWER` final est
juste l'environnement de test sans vraie carte son, `alsa: could not open ausrc
device`, pas lié à la sécurité).

**Portée** : ce changement (variable globale) s'applique à TOUS les postes internes,
sans exception, conformément à la demande de sécurité maximale de l'utilisateur.
**Hors scope / pas testé** : le comportement avec un trunk PSTN (aucun trunk actif
actuellement pour tester) — si un trunk est ajouté plus tard, il faudra vérifier
que `rtp_secure_media=mandatory` ne bloque pas les appels vers un fournisseur SIP
qui ne supporte pas SRTP (probable dans l'industrie) ; solution si ça arrive :
utiliser `rtp_secure_media_inbound`/`_outbound` par variable de canal ciblée sur le
dialplan du trunk plutôt que le défaut global, pour garder le mandatory seulement
entre postes internes.
Fichiers : sipv/backend/app/api/v1/endpoints/xml_curl.py (ajout dans `_user_xml()`,
laissé en place bien que non suffisant seul — inoffensif),
`/usr/local/freeswitch/conf/vars.xml` (nouveau `X-PRE-PROCESS`, sur 192.168.1.55),
`~/.baresip100/accounts`, `~/.baresip101/accounts` (`mediaenc=srtp-mand` ajouté, et
`module srtp.so` activé dans leurs `config` respectifs — changements de test
uniquement, pas applicables à de vrais téléphones qui gèrent SRTP nativement).

### ✓ TASK-S039.3 [x] Plage RTP personnalisée (évite conflit avec ports de jeux) (2026-07-24)
Contexte : l'utilisateur héberge aussi des serveurs de jeux (Icarus, Avorion,
Empyrion) sur le même réseau/routeur. La plage RTP par défaut de FreeSWITCH
(16384-32768) chevauchait presque tous ses ports de jeux déjà utilisés (17777,
27000-27021, 30000-30004 tombent tous dedans).
Fait :
- `switch.conf.xml` : `rtp-start-port`/`rtp-end-port` = 41000/43000 (2001 ports,
  largement suffisant — chaque appel actif utilise 1-2 ports). Choisi en dehors de
  toutes les plages de jeux courantes connues (Steam/Source 27000-27050, Minecraft
  25565, Rust 28015-28016, ARK/Satisfactory 7777-7778, DayZ/Valheim 2302-2458,
  7 Days to Die 26900-26902, Factorio 34197) en plus des ports déjà listés par
  l'utilisateur.
- Pare-feu SIPV : règle INPUT UDP mise à jour et persistée pour matcher (41000:43000
  au lieu de 16384:32768).
- **⚠️ Erreur commise puis reconnue** : une première version de ce changement
  (plage 20000-20200) a été implémentée suite à une simple QUESTION de l'utilisateur
  ("est-ce que je peux changer la plage ?") traitée à tort comme un GO — corrigé
  après que l'utilisateur l'ait signalé. Plage finale (41000-43000) refaite
  seulement après un GO explicite ("parfait on configure la plage 41000-43000").
  Noté en mémoire persistante (feedback_workflow_rules.md) pour éviter la récidive.
- `switch.conf.xml` n'est lu qu'au démarrage (comme `vars.xml`) — a nécessité un
  redémarrage complet de `freeswitch` (deuxième de la session, après celui pour
  SRTP). Validé après coup : profil `internal` toujours sur loopback, Kamailio
  toujours actif, les 2 postes de test ré-enregistrés sans problème, et un appel
  test confirme le port RTP réellement utilisé (42884) tombe bien dans la nouvelle
  plage, avec SRTP toujours actif (`RTP/SAVP` dans le SDP).
- **Non résolu, mineur** : la règle de marquage QoS (DSCP, priorisation du trafic
  vocal) référençant l'ancienne plage 16384-32768 n'a pas pu être mise à jour --
  le module DSCP d'iptables échoue sur ce serveur avec "Invalid argument" même
  pour un ajout simple (pas seulement une suppression), semble être un souci de
  compatibilité iptables/nftables propre à cet hôte, pas lié à mon changement.
  Règle laissée telle quelle (inoffensive, ne matche juste plus rien) -- QoS pour
  le RTP a perdu son marquage DSCP, aucun impact sur la sécurité ou la
  fonctionnalité des appels, seulement sur la priorisation réseau optionnelle.
**Port forwarding routeur (à faire par l'utilisateur, pas par moi)** : rediriger
`41000-43000 UDP` (au lieu de `16384-32768`) vers `192.168.1.55`, en plus de
`5061 TCP` déjà communiqué pour la signalisation.
Fichiers : `/usr/local/freeswitch/conf/autoload_configs/switch.conf.xml` (sur
192.168.1.55), pare-feu SIPV (`/etc/iptables/rules.v4`).

### ✓ TASK-S039.4 [x] Connexion SIP "conventionnelle" (serveur = IP, tenant via lien, pas via domaine) (2026-07-24)
Contexte : configurer Zoiper (et d'autres apps SIP grand public) a revele que
l'approche "domaine = tenant + outbound proxy separe" ne correspond PAS a comment
la majorite des vrais clients SIP fonctionnent (confirme par l'experience de
l'utilisateur avec des dizaines de fournisseurs VoIP) -- soit un sous-domaine DNS
unique par tenant (resout automatiquement), soit -- ce que l'utilisateur a demande
explicitement, a la maniere de ScopServ -- le tenant est lie au poste par une
VRAIE relation en base de donnees (deja le cas : `SIPExtension.tenant_id` est deja
une cle etrangere, PAS un prefixe de username parse), et le client SIP se connecte
juste avec une IP/DNS classique + username + password, sans jamais avoir besoin de
connaitre le nom du tenant.

**Root cause #1 (auth/REGISTER)** trouvee dans `_handle_directory` (xml_curl.py) :
le lookup cherchait le tenant par `Tenant.account_number == domaine_envoye` AVANT
meme de regarder le username -- si le domaine envoye ne matchait aucun tenant
(ex: le client met l'IP du serveur comme domaine), rejet immediat sans jamais
essayer de retrouver le poste par son username (deja globalement unique, verifie
a la creation). Fix : si le domaine ne matche aucun tenant, chercher le poste
directement par username, puis remonter au vrai tenant via `SIPExtension.
tenant_id` (la cle etrangere reelle).

**Piege trouve en testant (pas suppose)** : meme apres ce fix, FreeSWITCH
rejetait encore la reponse avec `403 Forbidden`. Verifie contre le code source
(`switch_xml.c`, `switch_xml_locate_domain`) : FreeSWITCH exige que le
`<domain name="...">` retourne corresponde EXACTEMENT au domaine demande dans la
requete originale (`switch_xml_locate("directory", "domain", "name", domain_name,
...)`), peu importe quel tenant est reellement trouve derriere. Fix : le
`<domain name="...">` externe echo maintenant le domaine BRUT envoye par le
client (`advertised_domain`), pendant que le contexte interne/routage continue
d'utiliser le VRAI domaine du tenant (`tenant.account_number`) pour
`user_context` et les autres variables.

**Root cause #2 (routage d'appel)** : meme probleme dans `_dialplan_internal` --
le tenant etait resolu uniquement via `variable_sip_from_host` (le domaine
d'origine de l'appelant). Capture reelle faite (pas suppose) via un appel
`loopback` simule pour confirmer le nom exact du champ portant le username
appelant : `variable_sip_from_user`. Fix : meme fallback que pour l'auth --
si le domaine ne matche aucun tenant, retrouver le tenant via le poste appelant
(`variable_sip_from_user` → `SIPExtension.tenant_id`).

**Validation complete** : poste de test temporairement bascule sur domaine
`192.168.1.55` (au lieu de `t1001`) -- REGISTER reussi (`200 OK`), ET un appel
simule (loopback) vers un autre poste du meme tenant atteint `Ring-Ready`
correctement (routage fonctionnel, pas juste l'auth). Poste remis dans son etat
d'origine apres test. Regression verifiee : les 2 postes de test sur le domaine
`t1001` normal fonctionnent toujours identiquement (REGISTER + appel + SRTP
intact).

**Consequence pratique pour l'utilisateur** : n'importe quelle app SIP (Zoiper,
Groundwire, un vrai telephone) peut maintenant se connecter avec juste
**Server = 192.168.1.55 (ou 142.112.42.52 a distance)**, **User = t1001-102**,
**Password**, sans jamais avoir besoin de connaitre ou taper `t1001` nulle part.
La connexion "avec domaine tenant explicite" (comme le GXP2135 est deja
configure) continue AUSSI de fonctionner -- les deux methodes marchent en
parallele, aucune des deux n'a ete retiree.
Fichiers : sipv/backend/app/api/v1/endpoints/xml_curl.py (`_handle_directory`,
`_directory_single_user`, `_handle_dialplan`, `_dialplan_internal`).

### TASK-S018.3 [ ] Fiche extension — identification, plan d'appel, renvois, DND
⚠️ ENTREE PERIMEE -- superseee par TASK-S018.3 [x] plus haut dans ce fichier (section
"Bloc 3 -- UX UCM", deja implementee et testee le 2026-07-23). Laissee ici telle quelle
(regle "ne jamais effacer une entree") plutot que supprimee.
Dépend de : TASK-S018 (fiche unifiée existante)
Champs : succursale/site (texte libre pour commencer), description courte ; plan
d'appel — autorisation interurbain/international (à clarifier au moment du code : champ
simple ou lien vers les OutboundRoute existantes comme classe de service) ; renvoi
immédiat (on/off + destination) ; renvoi sur occupation (+ délai + destination) ; renvoi
sans réponse (+ délai + destination) ; renvoi hors ligne / destination si non enregistré ;
DND activé + DND verrouillé (admin empêche l'utilisateur de le désactiver) ; réponse
automatique / intercom automatique ; nombre maximal d'appels simultanés (distinct de
`max_contacts` qui est le nb d'appareils enregistrés) ; codec — décision projet : PCMU
par défaut pour tout le projet (actuellement `codec` est nullable par poste sans défaut
projet, à trancher : défaut global codé en dur, ou champ Settings) ; sonnerie distinctive
vs par défaut ; enregistrement auto vs manuel (`record_calls` existe déjà en bool simple) ;
`max_contacts` — changer le défaut actuel (3) à 1 par défaut ; groupe(s) d'appartenance
(IVR/queue/ring group) affiché en lecture sur la fiche.
Fichiers cibles : sipv/backend/app/models/sip.py, api/v1/endpoints/extensions.py,
sipv/frontend (fiche extension unifiée existante, TASK-S018).

### TASK-S018.5 [x] Plan d'appel reellement applique (Canada/US/international/premium/NIP/limite)
Demande de l'utilisateur (2026-07-24, "mega prompt" fiche poste complete, GO explicite
"fait le dialing plan quand tu veux") : `call_permission` (S018.3) etait stocke et
reflete dans `toll_allow` du XML directory mais JAMAIS verifie par le dialplan --
n'importe quel poste pouvait composer n'importe quel numero peu importe le palier
configure. Cette tache cable reellement la verification, avec beaucoup plus de
granularite que le simple local/national/international d'origine (Canada et US
distingues, numeros payants/900 refuses par defaut, NIP d'autorisation, limite
monetaire mensuelle).

Fait :
- `app/core/nanp.py` (nouveau) : classification des numeros NANP -- le Canada et les
  USA partagent le meme format a 10 chiffres, impossible de les distinguer sans une
  table indicatif regional -> pays. `CANADIAN_AREA_CODES` = liste statique verifiee
  contre la liste NANPA publique (a mettre a jour si de nouveaux indicatifs sont
  assignes -- rare). `classify_number()` retourne local/us/canada/toll_free/premium/
  international, pas utilise directement par le dialplan (la classification se fait
  par regex FreeSWITCH, voir plus bas) mais reutilisable ailleurs si besoin (CDR,
  rapports).
- `SIPExtension` (migration `0029_call_permission_s018_5`) : `allow_canada`,
  `allow_us`, `allow_international`, `allow_premium` (tous nullable = herite du
  Tenant), `blocked_countries`/`blocked_prefixes` (CSV), `ld_pin` (NIP d'autorisation,
  chiffre Fernet -- meme pattern que le mot de passe SIP), `ld_monthly_limit`
  (Numeric, limite mensuelle en $), `preferred_trunk_id` (FK sip_trunks, override du
  trunk par defaut pour le NIP d'autorisation).
- `Tenant` : `default_allow_canada`/`default_allow_us` (true par defaut),
  `default_allow_international`/`default_allow_premium` (false par defaut, "refuser
  par defaut" comme demande), `default_blocked_countries`/`default_blocked_prefixes`,
  `default_ld_pin` (chiffre), `default_ld_monthly_limit` -- base de la chaine
  d'heritage (poste herite du tenant si null, meme principe que voicemail S008.2).
  Resolution explicite dans `_resolve_call_permission()` (xml_curl.py) plutot que
  `resolve_setting()` generique -- noms de champs differents entre les deux niveaux
  (meme raison que voicemail S008.2).
- `xml_curl.py::_call_permission_gate_entries()` : genere des entrees dialplan de
  REJET (`403 Forbidden`) placees AVANT `_outbound_dialplan_entries()` dans le
  document -- FreeSWITCH s'arrete a la premiere `<condition>` qui matche dans un
  contexte, donc l'ordre du document suffit a faire gagner le blocage sur la route
  qui bridgerait sinon l'appel (pas besoin de toucher `OutboundRoute` lui-meme).
  - Categories bloquees par regex NANP : premium (`^1?900[0-9]{7}$`), international
    (`^011(.+)$`), Canada (alternation des indicatifs de `CANADIAN_AREA_CODES`), US
    (meme alternation en negative lookahead PCRE `(?!...)` -- a valider en conditions
    reelles que FreeSWITCH accepte bien ce type de regex dans une condition dialplan,
    PCRE le supporte en theorie).
  - Pays/prefixes bloques : meme mecanisme, un entree de rejet par code/prefixe listé.
  - Limite mensuelle : requete `SUM(CDR.cost)` depuis le 1er du mois courant pour ce
    poste (meme source de verite que la facturation, pas de compteur separe a
    resynchroniser) -- si depassee, bloque tout numero externe.
  - NIP d'autorisation : composer `*80<NIP><numero>` outrepasse TOUS les blocages
    ci-dessus (simplification assumee, pas de bypass partiel par categorie). Le NIP
    dechiffre est compile directement dans le motif regex regenere a chaque lookup
    xml_curl (jamais ecrit en clair sur disque) ; bridge fait directement dans cette
    meme entree (pas de `transfer` -- un transfer redeclencherait un lookup xml_curl
    sur le numero nu qui repasserait par ces memes portes et annulerait le
    contournement). Trunk utilise : `preferred_trunk_id` du poste si defini, sinon le
    premier `OutboundRoute` actif du tenant par priorite.
- `extensions.py`/`tenants.py` : nouveaux champs exposes sur `ExtOut`/`ExtCreate`/
  `ExtUpdate` et `TenantOut`/`TenantUpdate` ; `ld_pin`/`default_ld_pin` acceptes en
  clair a l'entree, chiffres avant stockage, jamais renvoyes en clair (`has_ld_pin`
  bool seulement, meme pattern que les mots de passe admin telephone).

Deploye et teste en direct (2026-07-24) : rsync sur le serveur reel, migration 0029
appliquee (`alembic upgrade head` OK), sipv-backend ET sipv-backend-tls redemarres.
Simulation directe de POST xml_curl (section=dialplan, Caller-Context=sipv-internal,
Caller-Destination-Number=variable, variable_sip_from_user=t1001-100) confirme :
premium (900) et international (011) rejetes par defaut (heritent du Tenant),
Canada/US non bloques par defaut. Test de bascule reel : `allow_canada=false` pose en
DB sur t1001-100 -> l'entree `perm_canada` apparait bien dans le XML dialplan genere
pour un numero 514 (Montreal) ; remis a `NULL` (defaut) apres verification, confirme
en DB. Les 3 postes de test (t1001-100, t1001-101, GXP2135/t1001-102) restent
`Registered` sans interruption apres les 2 redemarrages de service.
Reste a faire (documente plutot qu'invente) :
- Portail gestionnaire (TASK-S029/S030/S031, pas encore construit) pour que le client
  reinitialise lui-meme sa limite mensuelle -- pour l'instant, seulement modifiable
  cote admin (ERPCRM fiche contact ou SIPV directement).
- Negative lookahead PCRE pas verifiee en conditions reelles (voir ci-dessus).
Fichiers : sipv/backend/app/core/nanp.py (nouveau), models/sip.py, models/tenant.py,
api/v1/endpoints/xml_curl.py, api/v1/endpoints/extensions.py,
api/v1/endpoints/tenants.py, alembic/versions/0029_call_permission_s018_5.py.

### TASK-S018.6 [x] Caller ID separe interne/externe + masquer + defaut compagnie
Demande de l'utilisateur (meme "mega prompt" que S018.5) : `caller_id_name`/
`caller_id_number` (S003) etaient un SEUL couple utilise a la fois pour
`effective_caller_id_*` (interne) et `outbound_caller_id_*` (externe) -- impossible
d'afficher un nom/numero different a un collegue interne vs a l'exterieur.

Fait (migration `0030_caller_id_split_s018_6`) :
- `SIPExtension.caller_id_internal_name/number`, `caller_id_external_name/number`
  (tous nullable), `hide_caller_id` (bool). Les anciens `caller_id_name/number`
  restent en DB et servent de fallback intermediaire (compat ascendante totale --
  une extension existante qui n'a que les anciens champs remplis continue de se
  comporter EXACTEMENT comme avant).
- `Tenant.default_caller_id_name/number` : defaut compagnie pour l'EXTERNE
  seulement (ex: numero principal de la compagnie) -- l'interne n'a pas de defaut
  compagnie, il retombe directement sur le nom/poste du contact.
- Chaine de resolution dans `_user_xml()` (xml_curl.py, qui prend maintenant
  `tenant` en parametre au lieu de juste le nom de domaine) :
  - interne : `caller_id_internal_name/number` -> `caller_id_name/number` -> `ext.name`/`ext.extension`
  - externe : `caller_id_external_name/number` -> `caller_id_name/number` -> `tenant.default_caller_id_name/number` -> `ext.name`/`ext.extension`
- `hide_caller_id` : emet `origination_privacy=hide_name:hide_number:screen`
  UNIQUEMENT sur le sortant (aucune variable ajoutee sur `effective_*`) -- un
  collegue interne doit toujours voir qui appelle, seul le monde exterieur ne doit
  pas voir le numero si l'utilisateur l'a demande.
- `extensions.py`/`tenants.py` : nouveaux champs exposes sur `ExtOut`/`ExtCreate`/
  `ExtUpdate`/`TenantOut`/`TenantUpdate`.

Deploye et teste en direct : migration 0030 appliquee, sipv-backend + sipv-backend-tls
redemarres, les 3 postes de test restent `Registered`. Test de bascule reel en DB sur
t1001-100 : `caller_id_external_name/number` + `hide_caller_id=true` poses ->
XML directory regenere confirme `effective_caller_id_name=Test Un` (interne
inchange) MAIS `outbound_caller_id_name=Simple IP inc.` (externe different) +
`origination_privacy` present ; tout remis a NULL/false apres verification.
Reste a faire : exposer cote ERPCRM (fiche contact) -- TASK-023.5, voir TASKERPCRM.md.
Fichiers : sipv/backend/app/models/sip.py, models/tenant.py,
api/v1/endpoints/xml_curl.py, api/v1/endpoints/extensions.py,
api/v1/endpoints/tenants.py, alembic/versions/0030_caller_id_split_s018_6.py.

### TASK-S023.6 [~] Typer les destinations de renvoi + cabler renvoi immediat/DND
Demande de l'utilisateur (meme "mega prompt") : les 4 destinations de renvoi
(`forward_*_destination`, S018.3) etaient du texte libre, pas typees (poste/BV/
externe/groupe d'appel/file/IVR/message demande dans la spec) -- et surtout, AUCUN
des 4 renvois n'etait reellement applique au dialplan malgre le champ `enabled`
(juste stocke, comme note honnetement dans S018.3).

Fait (migration `0031_forward_destination_types`) :
- 4 nouveaux champs `forward_*_destination_type` (defaut `extension` pour immediat/
  occupe, `voicemail` pour non-repondu/hors-ligne -- comportement le plus utile par
  defaut).
- `xml_curl.py::_forward_action_xml()` resout SEULEMENT 3 types pour l'instant :
  `extension` (bridge vers un autre poste), `voicemail` (boite vocale, du poste
  cible ou de soi-meme si vide), `ring_group` (reutilise l'entree `rg_<numero>` deja
  generee par `_ringgroup_dialplan_entries` via `execute_extension`). `external`
  (aucun trunk reel actif dans ce projet pour l'instant), `queue`/`ivr`/`message`
  (aucune convention de resolution etablie) sont acceptes en stockage mais PAS
  resolus -- si choisis, le renvoi ne s'applique pas et le poste sonne normalement
  (repli honnete, pas un bridge invente/casse).
- `_ext_dialplan_entries()` : SEULEMENT le renvoi IMMEDIAT et le DND sont reellement
  cables (le poste ne sonne pas du tout, redirige tout de suite -- pas besoin de
  detecter occupe/non-repondu). DND sans renvoi immediat configure va a la boite
  vocale si activee, sinon `486 Busy Here`.
- ⚠️ [~] et pas [x] : renvoi SUR OCCUPE et SUR NON-REPONSE restent stockes/typés
  mais PAS cables -- ils necessitent le patron FreeSWITCH bridge+`continue_on_fail`+
  verification de `${originate_disposition}` (ou conditions `<condition>` chainees
  dans la meme extension), plus intrusif sur la logique de bridge PARTAGEE par TOUS
  les postes (risque de casser l'appel interne normal si mal ecrit) et impossible a
  verifier honnetement dans cette session (aucun moyen simple de simuler un vrai
  "occupe" ou "non-repondu" avec les softphones de test qui ne repondent pas
  automatiquement). Pas fait a la sauvette -- a reprendre avec un vrai scenario de
  test (deux appels simultanes pour "occupe", laisser sonner pour "non-repondu").

Deploye et teste en direct : migration 0031 appliquee, sipv-backend + sipv-backend-tls
redemarres, les 3 postes de test restent `Registered`. Verifie que le cas de base
(aucun renvoi configure) produit une entree dialplan STRICTEMENT IDENTIQUE a avant
cette tache (aucune regression). Bascule reelle testee : `forward_immediate_enabled=
true` + destination extension `100` pose sur t1001-101 -> l'entree dialplan generee
bridge directement vers `100` au lieu de sonner `101` ; remis a `false`/`NULL` apres
verification.
Reste a faire : busy/no_answer wiring (voir ci-dessus) ; exposer les selecteurs de
type sur ERPCRM (TASK-023.5/ContactDetail.jsx).
Fichiers : sipv/backend/app/models/sip.py, api/v1/endpoints/xml_curl.py,
api/v1/endpoints/extensions.py, alembic/versions/0031_forward_destination_types.py.

### TASK-S023.7 [x] Statut d'appel en direct (en ligne / sonne) par poste
Demande de l'utilisateur : voir sur la fiche compagnie ET contact si un poste est
actuellement "en ligne" (icone combiné rouge) ou "sonne" (icone cloche jaune).

Fait :
- `esl.py::_parse_channel_states()` : parse `show channels as json`, classe chaque
  canal `ringing` (callstate RINGING/EARLY) ou `active` (callstate ACTIVE/HELD).
  Valeurs `callstate` confirmées par un VRAI appel de test (`originate ... &park`) --
  `RINGING` observé en direct pendant la sonnerie ; `ACTIVE`/`HELD` sont les valeurs
  documentées FreeSWITCH standard pour un appel répondu (pas observées avec un appel
  répondu réel dans cette session -- aucun softphone de test n'auto-répond -- mais
  ce sont des constantes du protocole `show channels`, pas devinées).
- `_lookup_call_state()` : matching par SOUS-CHAINE (pas exact) sur plusieurs champs
  (`cid_num`, `dest`, `callee_num`, `presence_id`, `initial_dest`) -- les champs
  FreeSWITCH contiennent souvent un suffixe (ex: `t1001-100-0x59ce73db8470` pour un
  softphone), un match exact aurait raté la détection (piège identifié en inspectant
  la vraie sortie JSON avant d'écrire le matching).
- `RegistrationOut.call_state` ajouté (idle/ringing/active), `tenant_registrations()`
  fait maintenant 2 appels ESL (registrations + channels) au lieu d'un seul, toujours
  un seul appel par TENANT (pas par poste) comme le reste de cet endpoint.

Testé en direct : appel de test (`originate ... &park` sur t1001-100) → l'endpoint
`GET /esl/registrations/tenant/{id}` retourne bien `call_state: "ringing"` pour
t1001-100 SEULEMENT (101/102 restent `idle`, confirmant que le matching par
sous-chaîne ne fait pas de faux positifs) ; après `hupall`, revient à `idle` pour
tous. Les 3 postes de test restent `Registered` sans interruption.
Reste à faire : côté ERPCRM (TASK-023.8) -- exposer `call_state` + statut
renvoi/DND sur CompanyDetail.jsx et ContactDetail.jsx (ce dernier n'affichait AUCUN
statut live avant cette tâche).
Fichiers : sipv/backend/app/api/v1/endpoints/esl.py.

### TASK-S023.9 [~] Ring groups reconstruits (priorité/ordre/exclusion/confirmation/horaire)
Demande de l'utilisateur : priorité du poste, ordre de sonnerie, confirmer avant de
répondre, poste temporairement exclu, horaire d'appartenance au groupe -- `RingGroup`
n'avait qu'un CSV `members` brut sans aucune de ces notions par membre.

Fait (migration `0032_ring_group_members_s023_9`, avec migration de DONNÉES -- pas
juste un schéma) :
- Nouvelle table `ring_group_members` (extension_id FK, priority, ring_order,
  temporarily_excluded). Le CSV `members` existant est parsé et migré automatiquement
  vers cette table pendant la migration (ordre CSV -> ring_order), aucune donnée
  perdue. `members` reste en DB comme LEGACY (règle "ne jamais supprimer une
  colonne sans demande") mais n'est plus la source de vérité pour le dialplan --
  seulement un repli si un groupe n'a aucun membre dans la nouvelle table (compat
  pour un éventuel groupe créé par un ancien chemin de code pas encore mis à jour).
- `RingGroup.confirm_before_answer`, `RingGroup.schedule_id` (FK schedules,
  réutilise TASK-S016 -- pas de nouveau modèle d'horaire).
- `xml_curl.py::_ringgroup_dialplan_entries()` réécrite : trie par `ring_order` puis
  `priority` en mode "hunt" (séquentiel), exclut les membres `temporarily_excluded`,
  vérifie l'horaire (`_is_schedule_open()`, dupliqué depuis `schedules.py` --
  assumé plutôt que refactoré pour ne pas toucher un endpoint déjà en prod, voir
  commentaire dans le code) et transfère vers `no_answer_destination` si le groupe
  est fermé, préfixe chaque cible de bridge avec
  `{group_confirm_key=1,group_confirm_file=...}` si `confirm_before_answer`.
- `ivr.py` : nouveaux endpoints `PUT /ring-groups/{id}` (name/strategy/ring_time/
  no_answer_destination/is_active/confirm_before_answer/schedule_id) et
  `POST/PUT/DELETE /ring-groups/{id}/members` (miroir exact du pattern QueueMember
  de TASK-S007.2).

⚠️ Bug trouvé et corrigé EN TESTANT (pas laissé tel quel) : `create_ring_group`
plantait en 500 (`MissingGreenlet`) -- appelait `_rg_out(rg)` sur un objet fraîchement
créé sans `ring_members` eager-chargé (accès lazy hors contexte async). Fix : refetch
avec `selectinload` après le commit (même pattern que `list_ring_groups`), et
`update_ring_group` avait le même risque latent -- `db.refresh()` retiré (inutile,
aucun champ à défaut serveur modifié) plutôt que risqué. Un ORPHELIN créé par la
1ère tentative ratée (l'INSERT avait réussi avant le crash de sérialisation) a été
retrouvé et nettoyé après coup.

Testé en direct de bout en bout (groupe de test "150", 2 membres réels
t1001-100/101) : ordre "hunt" respecté (101 ring_order=0 sonne avant 100
ring_order=1, confirmé dans le XML dialplan généré) ; exclusion temporaire
retire bien 101 du bridge (100 seul reste) ; `confirm_before_answer` ajoute
bien le préfixe `group_confirm_key` sur la cible restante. Tout supprimé après
coup (0 lignes `ring_groups`/`ring_group_members`). Les 3 postes de test TLS
restent `Registered` sans interruption après les 2 redémarrages.

⚠️ [~] et pas [x] : horaire (`schedule_id`) et `confirm_before_answer` testés
seulement au niveau génération XML (pas avec un vrai appel qui atteint réellement
`group_confirm_key` en pratique -- nécessiterait un softphone qui répond et appuie
une touche, hors de portée des clients de test actuels).
Fichiers : sipv/backend/app/models/ivr.py, models/__init__.py,
api/v1/endpoints/xml_curl.py, api/v1/endpoints/ivr.py,
alembic/versions/0032_ring_group_members_s023_9.py.

### TASK-S011.2 [x] Fiche physique du poste (ProvisionedPhone étendu)
Dépend de : TASK-S011 (provisioning existant)
Champs ajoutés sur `ProvisionedPhone` (migration `0021_phone_physical`, appliquée sur
SIPV, backend synchronisé/redémarré, testé en direct) : `serial_number`,
`hardware_version`, `encrypted_admin_password` (Fernet, même pattern que `ClientAccess`
côté ERPCRM — clé dérivée de `SECRET_KEY`, `cryptography` déjà présent dans le venv
SIPV, aucune nouvelle dépendance), `wifi_enabled`, `bluetooth_enabled`, `headset_used`,
`expansion_module`.
- `provisioning_status` : PAS un champ stocké — calculé à la volée depuis
  `last_provisioned` ("jamais" / "provisionné"). Pas de palier "en retard" : aucun seuil
  précis n'a été donné par l'utilisateur, je n'en invente pas un arbitraire (LOI 4).
- Mot de passe admin : jamais renvoyé en clair par défaut (`has_admin_password: bool`
  seulement) — nouvel endpoint `GET /provisioning/{id}/reveal-admin-password` pour le
  récupérer à la demande, même UX que `ClientAccess` côté ERPCRM.
- `PhoneUpdate` accepte maintenant `mac_address` : remplacement d'un appareil physique =
  PUT avec le nouveau MAC/SN sur le MÊME enregistrement, tout le reste (extension liée,
  config) reste attaché — confirmé avec l'utilisateur (2026-07-23).
- Nombre d'appareils enregistrés : ajouté à `GET /esl/registration/{username}` et
  `GET /esl/registrations/tenant/{id}` (`registered_count`). A nécessité de changer
  `_parse_registrations()` (esl.py) qui écrasait silencieusement les enregistrements
  multiples pour un même username (dict simple) → maintenant une liste par username.
- ⚠️ Bug pré-existant trouvé et corrigé en cours de route (pas dans le scope initial,
  mais directement lié à ce que je testais) : `GET /esl/registration/{username}`
  répondait TOUJOURS "Unregistered" même pour un poste réellement enregistré, depuis
  TASK-S018 (fiche extension, "Statut live"). Cause : `sofia_contact profile/user`
  exige `user@domain`, pas juste `user` — vérifié en direct sur FreeSWITCH
  (`sofia_contact internal/t1001-100` échoue, `.../t1001-100@t1001` fonctionne). Fix :
  l'endpoint fait maintenant une vraie requête DB (SIPExtension → Tenant.account_number)
  pour construire le domaine, au lieu de parser la chaîne. Revérifié après coup : les 2
  postes de test toujours `Registered(TLS)` sans interruption, et le statut affiché est
  maintenant correct (`registered: true` là où c'était `false` avant, à tort).
- `PhoneModel.max_accounts` : laissé tel quel (déjà 1 par défaut) — la vraie demande
  "bannir les tentatives en trop" est une règle de sécurité, traitée dans TASK-S014.2,
  pas ici.

Fichiers touchés : `backend/app/models/provisioning.py`,
`backend/app/api/v1/endpoints/provisioning.py`, `backend/app/api/v1/endpoints/esl.py`,
`backend/alembic/versions/0021_phone_physical_fields.py`,
`frontend/src/pages/ExtensionDetail.jsx` (nouveaux champs dans la section Provisioning +
compteur d'appareils enregistrés dans Statut live).

Testé en direct : création d'un poste test avec mot de passe admin chiffré, `reveal`
confirmé (décryptage correct), suppression du poste test après coup (pas de résidu) ;
`registered_count` confirmé exact (1) sur un poste réellement enregistré ; les 2
registrations TLS de test intactes après les deux redémarrages du service.
Fichiers cibles : sipv/backend/app/models/provisioning.py, api/v1/endpoints/provisioning.py.

### TASK-S011.3 [!] Configuration visuelle du modèle de téléphone (image cliquable)
⚠️ BLOQUÉ (2026-07-23) : nécessite la photo du GXP2135 que l'utilisateur a dit fournir
lui-même. Pas de photo = pas de coordonnées cliquables à concevoir contre une vraie
référence — sauté volontairement dans la boucle autonome (deviner un schéma de mapping
sans l'image serait de la conception à l'aveugle). Reprendre dès que la photo est fournie.
Dépend de : TASK-S011, TASK-S011.2
Premier modèle : Grandstream GXP2135 (photo à fournir par l'utilisateur). Nouvelle table
de mapping bouton (poste/modèle, position, type bouton — BLF/speed dial/extension/autre,
valeur, label) + coordonnées cliquables sur l'image ; popup au clic sur un bouton avec
save/cancel. Décision à prendre au moment du code : mapping stocké par PhoneModel
(template partagé) ou par ProvisionedPhone (par appareil physique) — probablement les
deux (le modèle définit les zones cliquables, l'appareil stocke les valeurs assignées).
Fichiers cibles : nouveau modèle SQLAlchemy (ex. phone_button.py), nouvel endpoint,
nouvelle page/composant frontend.

### TASK-S011.4 [ ] Auto-provisioning Grandstream (fichier cfg<MAC>.xml, zero-touch)
Demande de l'utilisateur (2026-07-24) : configuration réseau automatique du téléphone
au lieu de la configuration manuelle qu'on vient de faire à la main pour le GXP2135 —
référence P-codes Grandstream fournie par l'utilisateur (firmware 1.0.11.106), à
conserver précisément pour ne pas la reperdre. Distinct de TASK-S011.3 (mapping visuel
des boutons — les deux sont liés mais pas la même chose : S011.3 = zones cliquables sur
une photo, S011.4 = génération automatique du fichier de config réseau).

**Référence P-codes (compte SIP 1, confirmés contre le firmware 1.0.11.106)** :
```
P271 = 1              # Account 1 Active
P31  = 1              # SIP Registration
P270 = <nom>           # Nom du compte affiché
P47  = <serveur>:5061  # SIP Server (le "domaine"/tenant OU l'IP selon methode de connexion)
P48  = <proxy>:5061    # Outbound Proxy (toujours l'IP/DNS reelle)
P35  = <user>          # SIP User ID
P36  = <user>          # Authenticate ID (= P35 dans notre cas)
P34  = <password>      # Authenticate Password
P3   = <nom affiche>   # Nom affiche sur l'ecran
P130 = 2               # Transport : 0=UDP, 1=TCP, 2=TLS/TCP
P2329 = 1              # sip: vs sips: (1 = sips, requis avec TLS)
P40  = <port local>    # Port SIP LOCAL du telephone -- PAS le port serveur, ne pas
                        # mettre 5061 ici par erreur (piège identifié explicitement)
P138 = 20               # Delai de retry normal (secondes)
P26002 = 1200            # Delai de retry apres un 403 Forbidden (secondes, ici 20 min)
P95030 = 1              # Permet un redemarrage via SIP NOTIFY check-sync sans param reboot=
P212 = 2                # Protocole de provisioning : 0=TFTP,1=HTTP,2=HTTPS,3=FTP,4=FTPS
P237 = <url>             # Adresse du serveur de configuration
```

**Mécanisme de provisioning réseau (zero-touch)** :
1. Le fichier doit être nommé `cfg<mac-minuscule-sans-separateur>.xml` (ex.
   `cfgc074ad123456.xml`), servi en HTTPS (`P212=2`) depuis l'URL de `P237`. Un
   fichier générique `cfg.xml` sert de repli si le fichier par MAC n'existe pas.
2. Format XML officiel Grandstream : chaque P-code devient un élément `<PxxxxN>`
   dans une structure `<gs_provision version="1"><mac>...</mac><config version="1">
   ...</config></gs_provision>`.
3. Flux visé : SIPV génère `cfg<MAC>.xml` à la volée (basé sur `ProvisionedPhone.
   mac_address` + les identifiants du poste lié) → le téléphone le télécharge en
   HTTPS au démarrage ou lors d'un cycle de provisioning → applique `P271=1`/`P31=1`
   avec les vraies infos SIP → REGISTER envoyé automatiquement.
4. **Limite confirmée par l'utilisateur** : pas de P-code pour forcer le serveur à
   déclencher l'enregistrement à distance — c'est toujours le téléphone qui décide
   de s'enregistrer (au démarrage, au cycle de provisioning, ou après le délai de
   retry). Un `SIP NOTIFY check-sync` (permis par `P95030=1`) peut demander un
   redémarrage/reprovisioning, MAIS seulement si le téléphone a déjà une adresse de
   contact valide côté serveur — inutile pour une toute première installation
   (celle-là doit obligatoirement passer par le provisioning réseau initial, le Web
   GUI, ou DHCP option 66).

Pas commencé — inscrit pour ne pas perdre cette référence technique. Reste à
faire : endpoint SIPV qui génère le XML à la volée pour un `ProvisionedPhone`
donné, servi en HTTPS à une URL prévisible, et décision sur comment le téléphone
apprend cette URL au tout premier démarrage (DHCP option 66, ou configuration
manuelle unique de `P237` la première fois, à trancher avec l'utilisateur).

**Référence complète fournie par l'utilisateur (2026-07-24)** : templates P-code
officiels Grandstream pour TOUTE la gamme (pas juste GXP2135), déposés dans
`/home/simpleip/GrandStream/Template_Config_Pcode/config-template/` — un fichier
`.txt` (documentation complète des P-codes) + souvent un `.xml` (format alias/nom
convivial) par modèle/firmware, plus un sous-dossier `change_log/` par version.
Fichier pertinent pour le GXP2135 (firmware 1.0.11.106) :
`gxp2130_40_60_70_35_config_1.0.11.106.txt` (le nom générique couvre plusieurs
modèles de la même famille partageant le firmware). Aucune image trouvée dans ce
dossier malgré la mention de l'utilisateur — la seule photo disponible reste
`/home/simpleip/Photo/GXP2135_BOUTON.png` (fournie plus tôt, pour TASK-S011.3).
À consulter directement dans ces fichiers au moment d'implémenter plutôt que de
deviner un nom de P-code — volumineux, pas dupliqué ici.

### TASK-S008.2 [x] Voicemail — accueils audio, langue, politique globale/compagnie/poste
Dépend de : TASK-S008, décision transverse (héritage de settings, résolue plus haut)

Première tâche à réellement utiliser la chaîne d'héritage (comme prévu dans la décision
transverse). Créé cette fois : `TelephonySettings` (singleton, une seule ligne — id
généré à la migration) pour le niveau Global, et un champ `voicemail_delete_after_email`
nullable sur `Tenant` pour le niveau Compagnie. Pas de `ExtensionProfile` créé — rien
dans cette tâche n'a besoin d'un niveau "profil de poste" intermédiaire, ça restait
spéculatif (voir décision transverse).

⚠️ Écart volontaire vs le plan initial : `resolve_setting()` (le resolver générique)
n'est PAS utilisé tel quel ici — son design suppose le même nom de champ à chaque
niveau (`getattr` uniforme), mais `Tenant` est un modèle partagé (pas juste voicemail)
donc son champ s'appelle `voicemail_delete_after_email` alors que sur `VoicemailBox`
c'est juste `delete_after_email`. Plutôt que forcer des noms identiques pour faire
rentrer l'utilitaire, `_resolve_delete_after_email()` dans voicemail.py fait la
résolution explicite en 3 lignes — plus clair à lire qu'un getattr générique ici. Le
resolver générique reste disponible pour un futur cas où les noms coïncident vraiment.

Champs ajoutés (migration `0022_voicemail_s008_2`, appliquée + testée en direct) :
- `VoicemailBox.delete_after_email` devenu NULLABLE (None = hérite compagnie→global,
  valeur explicite = ce poste s'écarte volontairement). `max_message_length` défaut
  180s→300s (5 min, décision explicite).
- `language`, `transcription_enabled`, `temp_greeting_enabled`,
  `greeting_{unavailable,busy,name,temp}_path` (chemin du fichier uploadé, null = pas
  uploadé).
- `Tenant.voicemail_delete_after_email` (nullable, override compagnie).
- `TelephonySettings` (singleton) : `voicemail_delete_after_email`,
  `voicemail_max_messages`, `voicemail_max_message_length`, `voicemail_language`.

Endpoints :
- `GET`/`PUT /voicemail/global-settings` (le "Voicemail global" — pas un onglet Settings
  séparé, juste une section dépliable en haut de `VoicemailPage.jsx` : aucune page
  Settings n'existe encore côté SIPV, en créer une pour un seul groupe de réglages
  aurait été prématuré).
- `Tenant.voicemail_delete_after_email` exposé via `TenantUpdate`/`TenantOut` existants
  (pas de nouvel endpoint — réutilise le CRUD tenant déjà en place).
- `VoicemailOut` expose `delete_after_email` (brut, peut être null) ET
  `effective_delete_after_email` (résolu) — pour que l'UI puisse distinguer "hérité" de
  "explicitement configuré".
- Accueils audio : `POST/GET/DELETE /voicemail/{id}/greetings/{type}` (type ∈
  unavailable/busy/name/temp). Stockage sur disque (pas de mount statique public comme
  ERPCRM catalogue — les accueils vocaux sont plus sensibles que des photos de produit,
  donc téléchargement derrière `get_current_user`, jamais public).
- Optionnel/plus tard (explicitement noté par l'utilisateur, pas fait) : notification
  seule (SMS/push) au lieu du courriel complet.

Fichiers touchés : `backend/app/models/settings.py` (nouveau), `models/tenant.py`,
`models/voicemail.py`, `models/__init__.py`, `api/v1/endpoints/voicemail.py`,
`api/v1/endpoints/tenants.py`, `alembic/versions/0022_voicemail_s008_2.py`,
`frontend/src/pages/VoicemailPage.jsx` (section Voicemail global + modal Paramètres par
poste avec upload/download/suppression des accueils).

Testé en direct, entièrement via l'API (aucune donnée existante avant/après le test,
0 lignes `voicemail_boxes` avant et après) :
- Chaîne d'héritage complète confirmée à 3 niveaux : global=true → effective=true ;
  override compagnie=false → effective=false (compagnie gagne sur global) ; override
  poste=true → effective=true (poste gagne sur compagnie). Chaque niveau testé
  individuellement avec le bon résultat.
- Upload/download d'un accueil : contenu vérifié identique byte-for-byte après
  aller-retour, fichier nommé `{vm_id}_{type}.ext`, suppression retire le fichier ET la
  référence DB.
- Tous les réglages de test remis à l'état initial après coup (global, override
  compagnie, poste de test supprimé).
- Les 2 postes de test TLS toujours `Registered` sans interruption après les 2
  redémarrages du service pendant cette tâche.

### TASK-S014.2 [~] Onglet Sécurité — whitelist/blacklist par poste et compagnie + seuils F2B
Dépend de : TASK-S014 (ACLRule/BlockedIP/FraudRule existants)

⚠️ [~] et pas [x] volontairement : la partie "gestion des données" est faite et testée,
mais la partie "détection/blocage automatique" n'existe pas — ni avant cette tâche, ni
après. Trouvaille importante en auditant `security.py` avant de coder : ce module est
100% CRUD manuel (créer/lister/supprimer des événements, ACL, IPs bloquées) — RIEN
n'alimente `SecurityEvent`/`BlockedIP` automatiquement aujourd'hui. Aucun watcher ne
compte les échecs d'authentification SIP en temps réel. Donc :
- "Nombre de tentatives échouées avant blocage" (`FraudRule.max_failed_auth_attempts`,
  nouveau champ, défaut 5) : stocké, éditable via l'API — mais rien ne l'applique
  encore, pas de compteur de tentatives ratées qui déclencherait un blocage.
- Règle "poste déjà enregistré + nouvelle tentative ailleurs = suspect" : PAS
  implémentée. Nécessiterait un watcher temps réel (abonnement aux événements
  d'enregistrement FreeSWITCH via ESL, ou parsing de logs) — infrastructure distincte,
  pas construite ici. Ne pas présenter cette protection comme active.
- Autre trouvaille en cours de route (bonus, pas dans le scope initial) : `max_contacts`
  sur `SIPExtension` (déjà en place depuis avant, étendu en S018.3) n'est JAMAIS émis
  dans le XML directory (`xml_curl.py::_user_xml`) — vérifié par grep, aucun
  `<param name="max-contacts".../>` nulle part. FreeSWITCH n'applique donc AUCUNE
  limite d'enregistrements simultanés par poste actuellement, malgré le champ qui
  existe et qui est affiché dans l'UI. Pas corrigé ici : je ne suis pas sûr à 100% du
  nom/syntaxe exact du paramètre XML attendu par mod_sofia pour ce faire (pas trouvé de
  référence fiable sur ce serveur pour vérifier avant d'écrire), et une mauvaise config
  SIP silencieusement inefficace serait pire que ne rien faire. À vérifier avec la doc
  FreeSWITCH officielle avant de s'y attaquer — noté comme TASK-S018.4 potentielle,
  pas inventé à l'aveugle.

Ce qui EST fait et testé en direct (migration `0023_security_s014_2`) :
- `ACLRule.extension_id` (nullable, FK `sip_extensions`) : une règle peut maintenant
  être scopée à un poste précis, en plus de compagnie (`tenant_id`) ou globale (les
  deux null). `GET /security/acl?extension_id=...` filtre par poste.
- Nouvel endpoint `POST /security/acl/whitelist-extension/{ext_id}` : lit l'IP publique
  ACTUELLE du poste via ESL (réutilise `_parse_registrations()` de S011.2) et crée une
  règle `allow` en `/32` scopée à ce poste — exactement le bouton "ajouter à la
  whitelist depuis la fiche" demandé.
- `GET /esl/registration/{username}` (déjà étendu en S011.2) expose maintenant aussi
  `public_ip` et `is_blocked` (vérifie `BlockedIP` pour cette IP, en respectant
  `expires_at`). Affiché sur `ExtensionDetail.jsx` avec badge Bloqué/Non bloqué et le
  bouton whitelist.
- `Security.jsx` (onglet ACL) : nouvelle colonne "Portée" (Poste/Compagnie/Global).

Sur la dépendance à TASK-S039 notée dans le plan initial : S039 n'est pas en cutover
(le trafic live passe toujours directement par FreeSWITCH, voir TASK-S039), donc l'IP
publique affichée ici vient du mécanisme existant (`show registrations` de FreeSWITCH),
pas de Kamailio — fonctionne pour l'instant (testé avec les postes de test, IP =
192.168.1.55 car test local), mais reste potentiellement moins fiable pour un poste
distant derrière NAT tant que le SBC n'est pas en façade, comme prévu.

Fichiers touchés : `backend/app/models/security.py`, `api/v1/endpoints/security.py`,
`api/v1/endpoints/esl.py`, `alembic/versions/0023_security_s014_2.py`,
`frontend/src/pages/Security.jsx`, `frontend/src/pages/ExtensionDetail.jsx`.

Testé en direct : whitelist-extension créée avec la vraie IP du poste t1001-100 (via
ESL), filtrage ACL par extension_id confirmé, seuil `max_failed_auth_attempts`
enregistré/relu correctement. Tout supprimé après coup (0 lignes `acl_rules` et
`fraud_rules` avant et après le test). Les 2 postes de test TLS toujours intacts après
le redémarrage.

### TASK-S007.2 [x] Agents de file d'attente (QueueMember étendu)
Dépend de : TASK-S007 (queues existantes)

Trouvaille en auditant avant de coder (même démarche que S014.2) : le routage vers une
queue EST bien câblé dans le dialplan (`<action application="callcenter"
data="{queue}@default"/>` dans `xml_curl.py`), mais RIEN ne pousse jamais les queues/
agents de la DB vers le runtime `mod_callcenter` de FreeSWITCH (pas de
`callcenter_config queue load` / tier add nulle part dans le code). Donc appeler une
queue qui n'a jamais été chargée dans mod_callcenter échouerait en pratique. Comme pour
`toll_allow`/`max_contacts`, les nouveaux champs agent sont stockés et gérables, mais
PAS ENCORE poussés vers FreeSWITCH — même limite documentée honnêtement, pas cachée.

"Niveau de priorité" = le champ `penalty` déjà existant (convention ACD standard, plus
bas = priorité plus haute) — pas dupliqué avec un nouveau champ.

"Groupes de pickup"/"groupes de paging"/"autorisation d'intercepter" : replacés sur
`SIPExtension` plutôt que `QueueMember` — ce sont des concepts au niveau du POSTE
(interception de n'importe quel appel qui sonne, pas seulement les appels de queue),
pas de la file d'attente. Décision prise sans reconfirmer (champs déjà nommés dans la
tâche = déjà autorisés).

Champs ajoutés (migration `0024_queue_agent_s007_2`) :
- `QueueMember` : `agent_number`, `agent_password` (PAS chiffré — même convention que
  `SIPExtension.password`, valeur active nécessaire au système, pas juste consultable),
  `is_dynamic`, `auto_login`, `pause_allowed`, `pause_reasons` (CSV), `wrap_up_time_seconds`,
  `skills` (CSV).
- `SIPExtension` : `pickup_group`, `paging_groups` (CSV), `can_intercept_calls`.

Gap d'API comblé au passage : il n'existait AUCUN moyen de gérer les membres d'une
queue après sa création (`QueueCreate.members` = liste one-shot à la création
seulement, pas de PUT/POST/DELETE sur les membres). Ajouté :
`POST /ivr/queues/{queue_id}/members`, `PUT /ivr/queues/members/{member_id}`,
`DELETE /ivr/queues/members/{member_id}`.

Fichiers touchés : `backend/app/models/ivr.py`, `models/sip.py`,
`api/v1/endpoints/ivr.py`, `api/v1/endpoints/extensions.py`,
`alembic/versions/0024_queue_agent_pickup_s007_2.py`,
`frontend/src/pages/ExtensionDetail.jsx` (pickup/paging/interception dans la section
Renvois). UI de gestion des membres de queue (agent_number/skills/etc. dans
`IVRPage.jsx`) PAS faite dans cette passe — le backend est complet et testé via API,
l'UI de gestion détaillée des agents reste à faire séparément si besoin.

Testé en direct : queue de test créée, membre ajouté avec tous les nouveaux champs,
mis à jour (wrap-up + penalty), supprimé, queue supprimée. Champs pickup/paging/
intercept testés sur un poste réel puis remis à `null`/`true` (état par défaut). Tout
nettoyé (0 lignes `queues`/`queue_members` avant et après). Les 2 postes de test TLS
toujours intacts.

### TASK-023.10 [x] QueueMember : sonnerie même si occupé + plusieurs appels de file
2 champs manquants identifiés lors de la réconciliation de la grande liste utilisateur
(migration `0033_queue_ring_multi`) : `ring_even_if_busy`, `allow_multiple_queue_calls`.
Même limite que le reste du module queue (S007.2) : stockés/éditables via API, PAS
poussés vers `mod_callcenter` (aucun champ Queue/QueueMember ne l'est aujourd'hui).

⚠️ Piège Alembic découvert en déployant (à retenir pour toute future migration) :
`alembic_version.version_num` est `VARCHAR(32)` — mon premier nom de révision
(`0033_queue_member_ring_multi_s023_10`, 36 caractères) a fait planter la migration
en toute fin d'exécution (`StringDataRightTruncationError`) APRÈS que les
`op.add_column` avaient déjà été émis dans la même transaction — DDL transactionnelle
confirmée : tout annulé proprement (vérifié, aucune colonne orpheline). Renommé en
`0033_queue_ring_multi` (21 caractères). Toujours garder un nom de révision ≤ 32
caractères dans ce projet.

Testé en direct : file + membre de test créés avec les 2 nouveaux champs à `true`,
relu correctement via l'API, membre + file supprimés après coup (0 lignes
`queues`/`queue_members`). Les 3 postes de test restent `Registered`.
Fichiers : sipv/backend/app/models/ivr.py, api/v1/endpoints/ivr.py,
alembic/versions/0033_queue_ring_multi.py.

### TASK-023.11 [~] Intercom/paging granulaire
Au-delà de `paging_groups`/`can_intercept_calls` (S007.2), migration `0034_intercom_
paging` : `intercom_warning_tone`, `intercom_mic_muted_on_answer`, `paging_priority`,
`paging_allow_send`, `paging_allow_receive`, `paging_emergency`, `multicast_address`,
`multicast_port`, `forced_volume` sur `SIPExtension`.

Câblé (le seul des 9 champs qui l'est) : `auto_answer_enabled` (existait déjà depuis
S018.3, jamais câblé) déclenche maintenant un vrai auto-answer intercom -- préfixe le
bridge avec `{sip_h_Call-Info=<sip:intercom>;answer-after=0}`, convention SIP standard
reconnue par la plupart des téléphones de bureau (Grandstream/Polycom/Yealink).
Vérifié structurellement en direct (bascule réelle en DB sur t1001-101 -> le header
apparaît bien dans le bridge généré, remis à `false` après) -- PAS vérifié avec un
vrai décrochage automatique sur le GXP2135 physique de test (aurait fait sonner/
répondre un appareil réel sans demande explicite de l'utilisateur pour ce test précis,
pas fait à la sauvette).

⚠️ [~] : les 8 autres champs (tonalité, micro coupé, priorité/émission/réception/
urgence paging, multicast, volume forcé) sont stockés/éditables mais PAS câblés --
le paging multicast en particulier est surtout une config CÔTÉ TÉLÉPHONE (P-codes
Grandstream, TASK-S011.4, pas encore commencée) plutôt qu'une fonctionnalité
dialplan FreeSWITCH ; le micro coupé après réponse nécessiterait un script post-
réponse par UUID sans mécanisme établi dans ce projet pour l'instant. Documenté
honnêtement plutôt que deviné.
Fichiers : sipv/backend/app/models/sip.py, api/v1/endpoints/xml_curl.py,
api/v1/endpoints/extensions.py, alembic/versions/0034_intercom_paging.py.

### TASK-S010.2 [x] 911 par poste (pas seulement par DID)
Dépend de : TASK-S010 (E911Address/DID911Assignment existants — liés au DID, pas au poste)

Nouveau modèle `ExtensionE911Assignment` (table `extension_911_assignments`, migration
`0025_extension_911_s010_2`) — même principe que `DID911Assignment` (adresse partagée
`E911Address`, une seule assignation active par poste, contrainte unique sur
`extension_id`), avec `emergency_location` (précision dans le bâtiment), `floor`,
`office`, `alert_email`.

⚠️ Pas dupliqué "succursale" ici : `SIPExtension.site` existe déjà depuis TASK-S018.3 et
couvre exactement ce concept — le réutiliser plutôt que créer un deuxième champ pour la
même information (c'est littéralement le principe que l'utilisateur a insisté pour
respecter dans son propre système ERPCRM plus tôt cette session — appliqué ici aussi
sans qu'il ait eu à le redemander).

Endpoints (miroir des endpoints DID existants) : `GET/POST /e911/extension-assignments/
tenant/{tenant_id}`, `GET .../by-extension/{extension_id}`, `PUT/DELETE .../{assign_id}`,
`GET /e911/extensions-without-911/tenant/{tenant_id}` (alerte conformité, miroir de
`dids-without-911`).

Fichiers touchés : `backend/app/models/e911.py`, `models/__init__.py`,
`api/v1/endpoints/e911.py`, `alembic/versions/0025_extension_911_s010_2.py`,
`frontend/src/pages/ExtensionDetail.jsx` (nouvelle section "911 — localisation
d'urgence" : sélection d'adresse existante + emplacement/étage/bureau, renvoie vers
"Succursale / site" pour ce champ-là plutôt que de le dupliquer).

Testé en direct : adresse créée, assignée au poste 100, relue via `by-extension`,
poste correctement retiré de la liste "sans 911" (101/102 restent listés, confirmant
le filtre fonctionne), double assignation refusée (409), tout nettoyé après (0 lignes
dans les deux tables avant/après). Les 2 postes TLS toujours intacts.

### TASK-S020.2 [~] Monitoring poste temps réel
Dépend de : TASK-S020 (ESL), TASK-S020.1 (IP publique/privée par registration)

[~] volontairement — sur les 4 métriques demandées, 2 sont réellement câblées avec des
vraies données FreeSWITCH, 2 ne le sont pas (honnêteté plutôt qu'invention) :

**Réel et testé :**
- Ping SIP (`Ping-Status`/`Ping-Time`) + `EXPSECS` (secondes avant expiration —
  indique indirectement depuis quand le dernier keep-alive a eu lieu) : ces données
  existent dans FreeSWITCH mais SEULEMENT dans la sortie texte de
  `sofia status profile <p> reg` — PAS dans `show registrations as json` (déjà utilisé
  ailleurs). Nouveau parseur `_parse_sofia_reg_detail()` pour ce format texte
  spécifique (blocs séparés par ligne vide, `Clé:\tValeur`). Nouvel endpoint
  `GET /esl/monitoring/{username}`.
- Qualité d'appel (MOS, gigue, perte de paquets) : SEULEMENT si un appel est
  ACTIVEMENT en cours pour ce poste (ces métriques RTP n'existent tout simplement pas
  pour un poste juste enregistré, sans appel) — recherche du canal actif via
  `show channels as json` (nouveau, matché sur `cid_num`/`dest`), puis
  `uuid_getvar` sur les variables RTP du canal. ⚠️ Chemin "appel actif" implémenté
  selon les conventions documentées de FreeSWITCH mais PAS vérifié avec un vrai appel
  en cours dans cette session (aucun appel actif au moment du test, seulement des
  postes enregistrés au repos) — le chemin "aucun appel actif" (le cas normal la
  plupart du temps) est lui bien vérifié et fonctionne correctement.

**PAS fait, documenté plutôt qu'inventé :**
- "Dernier code erreur SIP" (401/403/...) : nécessiterait de capturer les événements
  d'échec SIP au moment où ils arrivent (subscription ESL aux événements sofia, ou
  parsing de logs) — même lacune que "détection F2B" en TASK-S014.2, rien ne le fait
  actuellement.
- "Historique" : pas de table de série temporelle créée. Un historique n'a de sens
  qu'avec un worker qui interroge régulièrement et persiste les lectures — pas
  construit ici (aurait été une table vide/décorative sans ce worker).

Fichiers touchés : `backend/app/core/esl.py` (nouvelles méthodes ESL :
`sofia_status_profile_reg`, `show_channels`, `uuid_getvar`),
`api/v1/endpoints/esl.py` (parseur + `GET /esl/monitoring/{username}`),
`frontend/src/pages/ExtensionDetail.jsx` (ping/expiry/qualité dans Statut live).

Testé en direct : ping-status/ping-time/expires_in_seconds corrects sur un poste
réellement enregistré (comparé à la sortie `fs_cli` brute) ; dégradation propre sur un
poste non enregistré (tout `null`, pas d'erreur) ; `active_call: false` correct en
l'absence d'appel. Les 2 postes de test TLS toujours intacts après le redémarrage.


### TASK-S040 [ ] App SIP mobile maison (softphone dédié SimpleIP)
Demande de l'utilisateur (2026-07-24), après avoir buté sur une incompatibilité SRTP
probable avec Zoiper (v2.10.20.4) en testant la connexion à distance depuis un
cellulaire — voir TASK-S039.4 pour le détail complet du troubleshooting.
But : construire une app mobile (iOS/Android) SimpleIP dédiée pour la connexion des
postes, plutôt que dépendre d'apps tierces (Zoiper, Groundwire, etc.) dont le support
SRTP/codecs varie et peut bloquer sans qu'on puisse le corriger nous-mêmes.
Contraintes/leçons à respecter, tirées de l'expérience réelle de cette session :
- SRTP obligatoire (`rtp_secure_media=mandatory`, TASK-S039.2) doit fonctionner
  nativement et de façon fiable — c'est justement ce qui a échoué avec Zoiper.
- Connexion "conventionnelle" doit marcher : Serveur = IP/DNS classique, User =
  username complet (ex. `t1001-102`), Password — le tenant se retrouve par lien en
  base (TASK-S039.4), jamais par un champ domaine séparé à comprendre par l'usager.
- TLS pour la signalisation (déjà en place, testé, fonctionnel).
- Pas encore scopé : plateforme (natif iOS/Android vs cross-platform type Flutter/
  React Native), librairie SIP a évaluer (PJSIP, Linphone SDK, etc. — a rechercher),
  fonctionnalités minimales (juste appels, ou aussi messagerie vocale/transferts/etc.).
Pas commencé — inscrit pour ne pas perdre le contexte des contraintes découvertes.
