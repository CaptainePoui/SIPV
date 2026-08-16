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

- **Observation (2026-08-07 nuit, pendant TASK-S048)** : les logs `sipv-backend`
  montrent un flot répété de `CDR ignore, tenant inconnu pour domaine '142.112.42.52'`
  — un appel entrant réel arrive déjà sur le serveur depuis une IP externe (pas une IP
  interne 192.168.x), mais le CDR est jeté car le domaine reçu (l'IP du trunk, pas un
  `account_number` de tenant) ne matche aucun tenant. À investiguer avec l'utilisateur :
  soit une vraie ligne SIP de production est déjà connectée et génère du trafic réel
  perdu silencieusement (perte de CDR = perte de facturation/traçabilité), soit c'est
  un scan/probe externe sans rapport. Pas d'action prise cette nuit (pas dans le scope
  demandé), juste signalé pour ne pas passer à côté.

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
| TASK-S046  | prompts        | Bibliothèque de phrases/annonces réutilisables par tenant (upload, style ScopServ)   |
| TASK-S047  | prompts wiring | Câblage réel des phrases dans IVR (greeting) + destinations DID/route "message"      |
| TASK-S048  | did routing fix| ⚠️ Bug critique corrigé : TenantDID n'était jamais synchronisé vers InboundRoute      |
| TASK-S049  | cdr tenant fix | ⚠️ Bug corrigé : CDR perdus (tenant introuvable) pour les appels via trunk sortant    |
| TASK-S050  | acl external   | Sécurité : ACL entrante sur le profil external limitée au proxy SIP du fournisseur   |
| TASK-S051  | ring group fix | ⚠️ Bug corrigé + fonctionnalité : chaîne illimitée de destinations de secours après un groupe d'appel sans réponse |
| TASK-S052  | audit renvois  | [~] Audit champs SIPExtension non câblés — busy/offline corrigés, call_permission/dnd_locked/queue limits en attente |
| TASK-S054  | server sip ips | Champs config `sip_inbound_ip`/`sip_outbound_ip` sur SipvServer + édition ERPCRM (onglet Serveur) |
| TASK-S055  | click to call  | [~] Écouter/enregistrer un fichier audio via appel réel à un poste (Mode 1 fait pour Phrases IVR ; MOH générique + Mode 2 enregistrement restent à faire) |

#### TASK-S055 [~] Écouter/enregistrer un audio via appel à un poste (générique)

Demande de l'utilisateur (2026-08-08, dictée textuellement -- voir aussi
TASKERPCRM.md TASK-029 côté UI) : un système générique, réutilisable pour
TOUS les enregistrements (pas juste MOH), avec deux modes distincts :

**Mode 1 -- "Faire écouter" (playback seul)**
- Bouton sur n'importe quel fichier audio existant (MOH pour commencer).
- Popup : choisir le TENANT (filtré aux tenants actifs SIPV) -- SAUF si on est
  déjà dans le contexte d'une compagnie précise (page fiche compagnie), auquel
  cas ce choix est sauté.
- Puis choisir le POSTE -- seulement les postes ACTIFS ET CONNECTÉS (enregistrés)
  du tenant sélectionné.
- Déclenche un appel réel vers ce poste qui joue le fichier choisi.

**Mode 2 -- "Enregistrer" (phrase IVR, onglet Phrases d'une compagnie)**
- Bouton "Enregistrer" sur l'onglet Phrases (IVR) d'une fiche compagnie.
- Popup : choix du poste (avec nom affiché) -- PAS de choix de tenant ici,
  déjà dans le contexte d'une compagnie donc déjà son tenant.
- Déclenche un appel vers ce poste. Script vocal demandé EXACTEMENT :
  1. Annonce : "quand vous aurez fini, appuyez sur # pour confirmer la fin de
     l'enregistrement"
  2. Enregistrement démarre, se termine sur `#`.
  3. Menu joué : "pour écouter la phrase, appuyez sur 1 ; pour enregistrer la
     phrase, appuyez sur 2 ; pour annuler l'enregistrement, appuyez sur 3"
     - 1 = rejoue la phrase enregistrée, puis représente le même menu.
     - 2 = sauvegarde définitivement la phrase (destination finale = la
       phrase IVR ciblée sur la fiche compagnie).
     - 3 = annule, jette l'enregistrement, raccroche.
  4. Si aucune touche : répète le menu (1/2/3) jusqu'à 3 fois, puis annule
     automatiquement si toujours aucune réponse (raccroche).

**Reconnaissance faite pendant la session (pas encore implémenté, juste
investigué)** :
- `app/core/esl.py` a déjà un client ESL fonctionnel avec `originate(endpoint,
  extension, context, caller_id_name, caller_id_number)` (bgapi, retourne un
  Job-UUID) -- MAIS non utilisé nulle part ailleurs dans le code actuellement
  (aucun appel à `esl.originate` trouvé hors de sa propre définition). Ce
  serait la première vraie feature à l'utiliser.
#### TASK-S055.1 [x] Mode 1 partiellement implémenté (Phrases IVR) + fix appel qui ne sonnait pas

Le endpoint `POST /prompts/{id}/call` (mode "Faire écouter" appliqué aux
phrases IVR, côté onglet Phrases d'une fiche compagnie) a été implémenté
pendant la session TASK-029 (ERPCRM) sans passer par un numéro de
sous-tâche formel ici -- noté après coup. Utilise `esl.originate_app()`
(bgapi + syntaxe `&app(args)`, pas de passage par dialplan).

Bug signalé par l'utilisateur (2026-08-10) : le poste 102 ne sonnait
jamais. Cause : `endpoint = f"user/{ext.username}@{tenant.account_number}"`
(ex: `user/t1001-102@t1001`) -- mais `internal.xml` force TOUS les
enregistrements SIP dans un seul domaine `sipv`
(`force-register-domain`/`force-subscription-domain`/
`force-register-db-domain` = `sipv`), peu importe le tenant. Confirmé en
testant en direct via `fs_cli` : `@t1001` → `USER_NOT_REGISTERED`,
`@sipv` → `+OK`, appel lancé. L'unicité des postes reste garantie par le
préfixe username (`t1001-102`), pas par le domaine SIP. Fix : endpoint
changé pour `user/{ext.username}@sipv` dans
`backend/app/api/v1/endpoints/prompts.py::call_prompt`.

`sipv-backend` + `sipv-backend-tls` redémarrés. Mode 2 (enregistrement
DTMF avec menu 1/2/3) toujours pas construit -- reste à faire.

#### TASK-S055.2 [x] Fix .1 insuffisant -- 2e bug de syntaxe ESL (espace non protégé dans caller_id_name)

Le fix du domaine (.1) était nécessaire mais pas suffisant : le bouton
"Appeler" dans l'UI retournait 200 OK côté ERPCRM (bgapi accepte
toujours la commande et renvoie un Job-UUID, succès ou non) mais le
poste ne sonnait pas. Log FreeSWITCH : `[ERR] Parse Error!` →
`Originate Resulted in Error Cause: 27 [DESTINATION_OUT_OF_ORDER]`.

Cause : `esl.py::originate_app()` construit la liste de variables
`{origination_caller_id_name=Ecoute Phrase}` -- SANS guillemets autour
de la valeur. Le nom utilisé pour ce call ("Ecoute Phrase") contient un
espace, ce qui casse le parseur de variables FreeSWITCH (il s'attend à
des paires `cle=valeur` séparées par virgules, un espace non protégé
termine la valeur prématurément). Mon test manuel via `fs_cli` avait
utilisé `caller_id_name="Test"` (un seul mot) -- ça a caché le bug
pendant la vérification du fix .1, d'où l'impression que "tantôt ça
marchait" alors que seul le scénario testé (un mot) fonctionnait.

Fix : guillemets simples systématiques autour de `caller_id_name`/
`caller_id_number` dans `originate()` ET `originate_app()` (syntaxe
FreeSWITCH standard pour échapper les valeurs à espaces/caractères
spéciaux dans un bloc `{vars}`). Re-testé en direct avec la valeur exacte
utilisée par le code ("Ecoute Phrase") : `+OK`, appel établi.

Fichiers : `backend/app/core/esl.py`. `sipv-backend` +
`sipv-backend-tls` redémarrés.

Confirmé par l'utilisateur (2026-08-10) : le bouton "Appeler" fait
maintenant sonner le poste et joue la phrase. Log FreeSWITCH 19:11:56
(après le restart de 19:10:59) : ring → answered → playback → hangup
normal, appel complet réussi depuis l'UI ERPCRM.

#### TASK-S055.3 [x] 1 seconde de silence ajoutée avant la lecture (temps de porter le combiné à l'oreille)

Demande de Philippe : le playback démarre immédiatement à la réponse
(décroché = son direct), pas le temps de porter le combiné à l'oreille.
Fix : nouvelle fonction `_copy_with_lead_silence()` dans `prompts.py` --
lit le WAV source (PCM, format vérifié : mono/16-bit/8000Hz, compatible
avec le module `wave` de la stdlib), préfixe 1 seconde de silence (zéros)
au même format, écrit le résultat dans le cache
(`prompts_cache/{prompt.id}.wav`) qui est ensuite joué par `playback()`.
Remplace le `shutil.copy2()` direct utilisé auparavant. Générique --
s'applique à toute phrase jouée via ce endpoint, peu importe sa durée
d'origine.

Fichiers : `backend/app/api/v1/endpoints/prompts.py`. Syntaxe vérifiée
(`ast.parse`), `sipv-backend` + `sipv-backend-tls` redémarrés.

⚠️ **Confirmé par Philippe : ce délai doit être le comportement PAR DÉFAUT
de toute écoute d'enregistrement par appel**, pas seulement pour les
Phrases IVR. Donc quand le Mode 1 générique (TASK-S055, "Faire écouter"
-- MOH, et tout autre fichier audio à venir) sera construit, il doit
réutiliser `_copy_with_lead_silence()` (déjà générique, prend n'importe
quel WAV PCM source) plutôt que de copier le fichier directement.

- `show_registrations()` / `sofia_contact(profile, user_at_domain)` déjà
  disponibles sur le client ESL -- utilisables pour filtrer les "postes
  actifs ET connectés" demandés dans les deux popups.
- `api/v1/endpoints/xml_curl.py` génère déjà le dialplan XML dynamique
  (mod_xml_curl) et utilise déjà l'app FreeSWITCH `record_session` ailleurs
  (`_record_action`, enregistrement d'appels internes/externes) -- même
  famille d'app FreeSWITCH à réutiliser, mais PAS le même besoin (ici il
  faut un vrai menu interactif avec `play_and_get_digits` -- min=1 digit,
  max=1, max tries=3, terminators vides, prompt = le menu 1/2/3, et une
  boucle "1 = réécouter puis revenir au menu" qui nécessite soit un
  `execute_extension` auto-référentiel, soit un script Lua/JS dédié --
  décision d'architecture PAS encore prise, à valider avant de coder).

Décisions/architecture à trancher avant de commencer (GO requis, ne pas
commencer sans confirmation explicite -- appels réels vers de vrais
téléphones) :
1. Static XML dialplan (chaînage `execute_extension`) vs script Lua/JS dédié
   pour la boucle du menu de confirmation (mode 2).
2. Où stocker le fichier temporaire pendant l'enregistrement avant
   confirmation (option 2 = sauvegarder), et comment le lier à la phrase
   IVR ciblée sur la fiche compagnie ERPCRM.
3. Nouvel endpoint SIPV (ex: `POST /api/v1/calls/listen`,
   `POST /api/v1/calls/record-phrase`) qui origine l'appel et retourne un
   identifiant de suivi (statut de l'appel/enregistrement) -- ERPCRM doit
   pouvoir savoir si l'appel a été répondu / le résultat.
4. Mode 1 générique "pour tous les enregistrements" -- MOH en premier mais
   prévoir que ça doit aussi marcher plus tard pour d'autres types de fichiers
   (greetings, phrases existantes, etc.) sans réécrire le mécanisme.

Dépend de : rien de bloquant techniquement (ESL + xml_curl existent), mais
travail neuf des deux côtés (SIPV dialplan/ESL + ERPCRM UI, voir TASK-029
dans TASKERPCRM.md).

#### TASK-S055.4 [x] Régression -- route `/call` + fixes .1/.3 perdus lors d'un déploiement (retrouvés et réappliqués)

Pendant TASK-029.14 (TASKERPCRM.md, retrait du forçage 8kHz dans
`prompts.py`), un rsync depuis le dépôt git local `/home/simpleip/sipv` (sur
la machine ERPCRM) a écrasé `prompts.py` sur ce serveur avec une copie qui
n'avait jamais reçu les ajouts de TASK-S055/S055.1/S055.3 (faits
directement ici, jamais resynchronisés vers ce dépôt). Résultat temporaire :
route `/call` disparue (404), puis après reconstruction depuis la doc,
domaine SIP redevenu `@{tenant}` au lieu de `@sipv` (perte du fix .1) et
silence de tête absent (perte du fix .3) -- 200 OK côté API mais poste muet.
Les deux fixes ont été relus ici et réappliqués à l'identique. Reconfirmé
par les logs FreeSWITCH réels : Ring-Ready → answered → playback →
`NORMAL_CLEARING`.

**Aucun changement de comportement voulu** -- seulement une remise en état.
Fichiers : `backend/app/api/v1/endpoints/prompts.py`.
Dépend de : TASK-S055, TASK-S055.1, TASK-S055.3.

#### TASK-S056 [x] Audit config centralisée -- éliminer les IPs/chemins codés en dur restants

Lien TASKERPCRM : TASK-031 (détail complet côté ERPCRM). Fait le 2026-08-16
(session autonome, GO global de Philippe) -- audit complet des IPs codées en
dur : aucune trouvée côté ERPCRM (déjà propre). Côté SIPV, 13 chemins
absolus codés en dur trouvés à travers 6 fichiers, tous éliminés :
- `config.py` -- 2 nouvelles racines : `APP_DIR` (`/home/sipv/sipv`) et
  `FREESWITCH_DIR` (`/usr/local/freeswitch`) -- déménager ce serveur = changer
  seulement ces 2 lignes (+ `SIPV_HOST`/`SIPV_PUBLIC_IP` déjà existants)
- `voicemail.py`, `moh.py`, `prompts.py` -- `UPLOAD_DIR` dérivé de `APP_DIR`,
  `MOH_CALL_CACHE_DIR`/`PROMPT_CACHE_DIR` dérivés de `FREESWITCH_DIR`
- `xml_curl.py` -- `PROMPT_DIR`/`_RECORDINGS_DIR` idem
- `core/local_stream.py` -- `LOCAL_STREAM_INCLUDE_DIR`/`MOH_SOUNDS_BASE`/
  `MOH_UPLOAD_DIR` idem
- `core/erpcrm_client.py` -- `_CA_PATH` idem
- `workers/backup_runner.py` -- 2 entrées `CONFIG_PATHS` idem (déjà
  partiellement centralisé via `BACKEND_DIR` dynamique, complété pour
  cohérence)

Vérifié AVANT déploiement : toutes les valeurs calculées comparées aux
littéraux d'origine (assert Python) -- identiques, aucun changement de
comportement. Backend redémarré, `sipv-backend`/`-tls` actifs. Non touchés
volontairement : `/etc/kamailio/kamailio.cfg` et `/etc/freeswitch/vars.xml`
(chemins d'installation standard des paquets système, pas vraiment
variables même après un déménagement de serveur -- pas de sur-ingénierie
pour un cas qui n'arrive pas en pratique).
Commit + push directement depuis SIPV (`git@github.com:CaptainePoui/SIPV.git`).

#### TASK-S049 [x] Bug — CDR perdus pour les appels via trunk (résolution tenant sur sip_from_host)
Découvert le 2026-08-07 matin en investiguant une question de l'utilisateur ("j'ai ma
ligne test 5143222112 c'est de là que vient l'appel ?") sur les logs répétés `CDR
ignore, tenant inconnu pour domaine '142.112.42.52'` (Aug 01 → Aug 06, en rafales
quotidiennes). Investigation :
- `142.112.42.52` = l'IP publique DU SERVEUR SIPV lui-même (`Ext-SIP-IP` confirmé via
  `sofia status profile external`), PAS une IP externe suspecte — donc PAS un appel
  fantôme/scan comme l'utilisateur le craignait au départ.
- Le vrai trunk (ScopServ, gateway `t1001-gw-1e083163`) est bien enregistré en TLS
  vers `vgw1.simpleip.scopcloud.com` (173.242.190.133, `REGED` confirmé) — la ligne
  de test `15143222112` est légitime et fonctionnelle.
- Cause réelle : `cdr.py::ingest_cdr()` résolvait le tenant via
  `variables.get("sip_from_host") or variables.get("domain_name")` — `sip_from_host`
  (valeur SIP brute calculée par FreeSWITCH) passait EN PREMIER, alors que
  `domain_name` est LA valeur que notre propre dialplan fixe explicitement
  (`set domain_name={account}`) sur chaque branche pour identifier le tenant. Pour un
  appel acheminé via le trunk sortant, `sip_from_host` valait l'IP externe du serveur
  (pas "t1001"), donc `sip_from_host` était toujours vrai (jamais vide) et
  `domain_name` n'était jamais consulté → CDR perdu (silencieusement, `+OK` renvoyé
  quand même à FreeSWITCH pour ne pas faire échouer l'appel).
Fait : ordre de priorité inversé — `domain_name` tenté en premier, `sip_from_host` en
filet de secours seulement.
Testé : POST synthétique vers `/api/v1/cdr/ingest` reproduisant exactement le
scénario du bug (`domain_name=t1001`, `sip_from_host=142.112.42.52`) → CDR créé et
rattaché au bon tenant, confirmé en base puis nettoyé. Aucune nouvelle occurrence de
"tenant inconnu" dans les logs depuis le déploiement du correctif.
Fichiers : `backend/app/api/v1/endpoints/cdr.py`. Déployé sur le serveur réel,
`sipv-backend`/`sipv-backend-tls` redémarrés.

#### TASK-S050 [x] Sécurité — ACL entrante sur le profil "external" (trunks PSTN)
Demande explicite de l'utilisateur (2026-08-07 matin) : même pratique que sur ses
autres serveurs — n'accepter le trafic SIP entrant que depuis le proxy du
fournisseur, pour éviter les appels fantômes d'un scan/bot. Constat avant
correctif : le profil `external` de FreeSWITCH n'avait **aucune** ACL entrante
(`acl.conf.xml` ne définissait que `lan` et `domains`, `external.xml` n'avait aucun
`apply-inbound-acl`) — le port SIP du trunk était grand ouvert à n'importe quelle IP
sur Internet.
Fait :
- Nouvelle liste `sipv-trunks` dans `acl.conf.xml` (`default="deny"`), avec
  `allow cidr="173.242.190.133/32"` (IP résolue de `vgw1.simpleip.scopcloud.com` au
  moment de l'écriture).
- `apply-inbound-acl=sipv-trunks` ajouté au profil `external` (`sip_profiles/
  external.xml`).
- ⚠️ Bug rencontré en écrivant le commentaire XML du changement : un double tiret
  ` -- ` à l'intérieur d'un commentaire XML (invalide selon la spec XML) a cassé le
  parsing (`[error near line 85]: unclosed <!--`) au premier `reloadxml`. Corrigé
  immédiatement (tirets remplacés par une ponctuation normale) avant de continuer —
  vérifié avec `reloadxml`/`reloadacl` propres ensuite, aucune trace résiduelle.
Testé : API `acl` de FreeSWITCH (`fs_cli -x "acl <ip> sipv-trunks"`) — IP du
fournisseur → `true` (autorisée), IP du serveur lui-même et IP quelconque → `false`
(refusées). Gateway `t1001-gw-1e083163` toujours `REGED` après le restart du profil,
`ping` OPTIONS réussi juste après (`state UP`), `/api/health` du backend vérifié
sain, aucune anomalie dans les logs FreeSWITCH après coup.
⚠️ Limite connue, à surveiller : l'ACL n'autorise qu'UNE seule IP (résolution DNS au
moment de l'écriture). Si le fournisseur (ScopServ) utilise un pool de plusieurs
IP/SBC pour ce trunk, ou si cette IP change, de vrais appels entrants pourraient être
bloqués sans avertissement — à confirmer avec ScopServ (plage CIDR officielle si
disponible) plutôt que de se fier à une résolution DNS ponctuelle.
Réversible : sauvegardes faites avant modification —
`/usr/local/freeswitch/conf/autoload_configs/acl.conf.xml.bak_20260807` et
`sip_profiles/external.xml.bak_20260807`.
Fichiers (config serveur, hors dépôt git) : `acl.conf.xml`, `sip_profiles/
external.xml` sur 192.168.1.55.

#### TASK-S051 [x] Bug + fonctionnalité — chaîne illimitée de destinations après un groupe d'appel sans réponse
Demande de l'utilisateur (2026-08-07 matin), reformulée après plusieurs sessions
sans suite ("ça fait plusieurs fois que je te le demande... c'est le concept de
serveur SIP que je veux") : pouvoir ajouter autant de destinations de secours qu'il
veut après un groupe d'appel (actuellement : raccroche après le `ring_time`, 20s par
défaut). Voir [[feedback_log_verbal_requests_immediately]] — cette demande n'était
tracée nulle part avant cette session, d'où la frustration légitime.

Constat en creusant (bug réel, pas juste une fonctionnalité manquante) :
`RingGroup.no_answer_destination` existe dans le modèle/API depuis TASK-023.9 mais
n'était JAMAIS lu par `_ringgroup_dialplan_entries()` (`xml_curl.py`) dans le cas
"groupe ouvert avec membres actifs" — seul le cas "groupe fermé par horaire"
l'utilisait. Un champ configurable, visible dans l'API, qui ne faisait strictement
rien en pratique — même famille de bug que TASK-S047/S048 la même nuit.

Fait :
- Nouveau modèle `RingGroupFailoverStep` (`models/ivr.py`) : `ring_group_id`,
  `step_order`, `destination_type` (extension/ivr/queue/voicemail/hangup),
  `destination`, `ring_seconds` (uniquement pour `extension` — combien de temps
  sonner cette étape avant de passer à la suivante). Liste ordonnée, longueur
  illimitée — remplace `no_answer_destination` (champ conservé en base pour
  compat/lecture, plus lu par le dialplan, marqué `⚠️ LEGACY` dans l'API).
- Migration `0057_ring_group_failover_steps.py` : crée la table + backfill (aucune
  ligne trouvée en pratique — aucun groupe d'appel n'existait encore).
- `api/v1/endpoints/ivr.py` : CRUD complet (`POST/PUT/DELETE .../failover-steps`),
  `step_order` auto-incrémenté si omis à la création ; `RingGroupOut` expose
  `failover_steps` (chargé trié par `step_order` via la relation ORM).
- `api/v1/endpoints/xml_curl.py::_ringgroup_dialplan_entries()` : le dialplan émet
  maintenant `hangup_after_bridge=false` puis une action `bridge` par étape en
  séquence (comportement natif FreeSWITCH : une action qui échoue laisse la main à
  la suivante dans la même `<condition>`) — voicemail/ivr/queue/hangup terminent
  la chaîne, `hangup NORMAL_CLEARING` final explicite par sécurité.
  ⚠️ Bug trouvé et corrigé EN TESTANT (pas laissé tel quel) : les étapes de type
  "extension" passaient le numéro nu directement à `_bridge()` sans reconstruire le
  username complet préfixé par le tenant (`t1001-101`), contrairement à la
  convention déjà établie (TASK-023.29) — aurait échoué sur un vrai appel
  (`user/101@sipv` ne correspond à aucune entrée réelle de l'annuaire). Fonction
  signature étendue avec le paramètre `account`, même reconstruction que
  `_inbound_actions_for`.
Testé de bout en bout sur le serveur réel (groupe jetable, jamais un groupe de
production) : création d'un groupe + 3 étapes (poste 101 10s, poste 102 8s,
messagerie 100) → simulation d'un vrai lookup dialplan FreeSWITCH → XML confirmé
avec le bon enchaînement et les bons usernames préfixés ; suppression d'une étape →
XML mis à jour correctement ; groupe et étapes supprimés après validation.

Côté ERPCRM (proxy + UI, même session) :
- `backend/app/core/sipv_client.py` : `add/update/remove_ring_group_failover_step`.
- `backend/app/api/v1/endpoints/companies.py` : `POST/PUT/DELETE
  /companies/{id}/ring-groups/{rg_id}/failover-steps` (proxy).
- `frontend/src/pages/CompanyDetail.jsx` (`RingGroupsSection`) : dans le détail
  déplié d'un groupe, section "Si personne ne répond après Xs" — liste numérotée
  des étapes (type + valeur + secondes si poste), bouton "+ Ajouter une
  destination" réutilisable autant de fois que voulu, ✕ par étape.
Testé de bout en bout via le proxy ERPCRM (compagnie "Simple IP inc.") : création
groupe + étape + relecture confirmée, données de test supprimées après validation.
Build frontend vérifié (`npm run build` OK), servi en direct (`vite preview`, pas de
redémarrage requis).
Fichiers SIPV : `backend/app/models/ivr.py`, `models/__init__.py`,
`api/v1/endpoints/ivr.py`, `api/v1/endpoints/xml_curl.py`,
`alembic/versions/0057_ring_group_failover_steps.py`.
Fichiers ERPCRM : `backend/app/core/sipv_client.py`,
`api/v1/endpoints/companies.py`, `frontend/src/pages/CompanyDetail.jsx`.

#### TASK-S052 [~] Audit des champs SIPExtension stockés mais jamais câblés (renvois busy/offline)
Demande explicite de l'utilisateur (2026-08-07 matin, suite à TASK-S051) : "la
plupart des options ont des options, quand on fait une portion il faut mettre
toute la portion pas juste le début" — voir [[feedback_complete_the_whole_portion]].
Audit des champs `SIPExtension` documentés `⚠️ PAS ENCORE APPLIQUÉ`/`AUCUNE ACTION
RÉELLE` depuis TASK-S018.3 (2026-07-17), pour voir lesquels avaient été réglés
depuis (beaucoup l'ont été dans des sessions séparées, jamais cross-référencées
dans la note d'origine) et lesquels restaient vraiment inertes.

État constaté par champ :
- `forward_immediate_enabled` : déjà câblé (TASK-023.6).
- `dnd_enabled` : déjà câblé (TASK-023.6).
- `auto_answer_enabled` : déjà câblé (TASK-023.11, intercom).
- `forward_no_answer_enabled` + délai : déjà câblé (TASK-023.30/S023.31).
- `forward_busy_enabled/destination` : **PAS câblé — corrigé cette tâche.**
- `forward_offline_enabled/destination` : **PAS câblé — corrigé cette tâche.**
- `call_permission` (local/national/international, S018.3) : toujours PAS câblé
  pour de vrai — voir "Décision requise" plus bas, pas corrigé sans réponse.
- `dnd_locked` : aucun appelant nulle part (ni SIPV ni ERPCRM) — voir "Bloqué" plus bas.
- `max_concurrent_calls` : toujours pas câblé — pas traité cette session (voir
  "Reste à faire").
- `QueueMember.ring_even_if_busy`/`allow_multiple_queue_calls` (TASK-023.10) :
  toujours pas câblés — voir "Bloqué" plus bas (même prérequis que MOH/TASK-S033).

Fait (`forward_busy`/`forward_offline`) :
- `api/v1/endpoints/xml_curl.py::_ext_dialplan_entries()` : structure purement
  additive — une extension SANS `forward_busy_enabled` ni `forward_offline_enabled`
  génère EXACTEMENT le même XML qu'avant cette tâche (vérifié caractère pour
  caractère, voir tests plus bas). Seule une extension qui active l'un des deux
  bascule sur une forme `<extension continue="true">` à conditions multiples :
  bridge d'abord, puis `<condition field="${originate_disposition}"
  expression="^USER_BUSY$">` pour le renvoi occupé, `expression="^(NO_ROUTE_
  DESTINATION|SUBSCRIBER_ABSENT|UNALLOCATED_NUMBER)$"` pour le renvoi hors ligne,
  puis un dernier `<condition>` catch-all identique au comportement historique
  (sert de filet de sécurité si aucune des deux causes ne matche).
  Réutilise `_forward_action_xml()` déjà existant (poste/BV/groupe d'appel).
Testé : (1) régression — dialplan d'un poste sans busy/offline configuré comparé
avant/après le déploiement, identique caractère pour caractère (postes 100/101/102
réels) ; (2) nouvelle fonctionnalité — activé temporairement sur le poste de test
101 (`forward_busy` → messagerie, `forward_offline` → poste 100), XML généré
confirmé avec la structure multi-condition attendue ; poste remis à son état
d'origine après le test, dialplan reconfirmé identique à l'état "avant".
⚠️ [~] Ce qui N'EST PAS validé : la valeur EXACTE de `${originate_disposition}`
FreeSWITCH pour chaque cause. `USER_BUSY` est une valeur standard bien documentée ;
les 3 valeurs choisies pour "hors ligne" (`NO_ROUTE_DESTINATION`/
`SUBSCRIBER_ABSENT`/`UNALLOCATED_NUMBER`) sont les plus plausibles pour un `user/`
non enregistré mais pas confirmées avec un vrai appel vers un poste réellement
débranché/éteint (aucun softphone disponible cette session pour le tester). Le
mécanisme est conçu pour ne jamais régresser si les valeurs s'avèrent différentes
(retombe simplement sur le comportement no-answer historique) — mais le
routage busy/offline SPÉCIFIQUE reste à confirmer avec un vrai test d'appel avant
de le considérer pleinement fiable en production.

Décision requise avant d'aller plus loin sur `call_permission` : il existe DEUX
systèmes de plan d'appel parallèles sur `SIPExtension` — le tri-état
`call_permission` (local/national/international, S018.3, décoratif aujourd'hui,
sert seulement au `toll_allow` du XML directory) ET les champs granulaires
`allow_canada`/`allow_us`/`allow_international`/`allow_premium`/pays-préfixes-
bloqués (S018.5, RÉELLEMENT appliqués via `_call_permission_gate_entries()`). Pas
corrigé sans confirmation : deviner un mapping local/national/international ↔
Canada/US/international/premium risquerait de créer soit une fausse sécurité (si
le mapping est trop permissif) soit de bloquer des appels légitimes (si trop
restrictif) — exactement le genre d'erreur que ce projet évite explicitement
depuis TASK-S018.3 ("pas faite ici pour ne pas présenter une fausse sécurité"). À
trancher avec l'utilisateur : garder les deux (call_permission mappé en plus, en
ceinture-et-bretelles) ou retirer le simple tri-état de l'UI puisqu'il est
redondant avec le système granulaire déjà actif.

**Tranché (2026-08-07, même matin)** : Philippe confirme "Local/National/
International pas besoin avec les cases Canada/US/international/premium" — retiré.
`ExtensionDetail.jsx` : select + `CALL_PERMISSIONS` supprimés de la carte
"Identification & plan d'appel" (ne reste que succursale/description). Champ
`SIPExtension.call_permission` et `toll_allow` dans le XML directory laissés en
place tels quels (décoratifs, pas nuisibles, cohérent avec le pattern déjà établi
ailleurs dans ce projet de garder un champ LEGACY plutôt que de le purger sans
raison) — seule la confusion côté UI est retirée. Build frontend vérifié
(`npm run build` OK).

Bloqué (prérequis plus gros, pas juste un champ à câbler) :
- `dnd_locked` : censé empêcher un utilisateur du portail client de désactiver le
  DND lui-même si l'admin l'a verrouillé — mais AUCUN code n'existe encore nulle
  part (ni SIPV ni ERPCRM) qui permette à un utilisateur portail de modifier
  `dnd_enabled` (TASKERPCRM TASK-019 "Portail Mon poste", `[ ]` jamais commencé).
  `dnd_locked` n'a donc littéralement rien à verrouiller pour l'instant — pas un
  bug de câblage, une fonctionnalité qui dépend d'une autre pas encore construite.
- `QueueMember.ring_even_if_busy`/`allow_multiple_queue_calls` : même blocage que
  TASK-S033 (MOH) découvert cette même nuit — `callcenter.conf.xml` n'est jamais
  généré dynamiquement (`_handle_configuration()` ne gère que `ivr.conf`), donc
  mod_callcenter tourne sans AUCUNE config par tenant. Câbler ces 2 champs sur un
  système qui n'existe pas encore aurait été décoratif.

Reste à faire (pas bloqué, juste pas fait cette session par manque de temps) :
- `max_concurrent_calls` : mécanisme FreeSWITCH le plus probable = `mod_limit`
  (`<action application="limit" data="hash {compte}_{poste} calls {max}"/>` avant
  le bridge) — pas implémenté, sémantique exacte voulue (limite les appels
  ENTRANTS vers ce poste ? les appels total incluant sortants ?) pas confirmée.

Fichiers : `backend/app/api/v1/endpoints/xml_curl.py`.

#### TASK-S054 [x] Champs config canaux SIP (IP entrante/sortante) sur le serveur
Demande de l'utilisateur (2026-08-07) : son fournisseur SIP lui indique qu'il
faudra 2 IP publiques distinctes pour les canaux — une pour les appels entrants,
une pour les sortants. L'utilisateur ne connaît pas encore ces IP (à confirmer
avec le fournisseur) — demande explicite de construire les CHAMPS/réglages, pas
d'inventer ou deviner des valeurs.
Fait :
- `models/server.py` (`SipvServer`) : `sip_inbound_ip`/`sip_outbound_ip`
  (nullable, String(45), IPv4/IPv6). `ip_address` existant conservé tel quel
  (référence générale, pas remplacé).
- Migration `0058_server_sip_channel_ips.py`.
- `api/v1/endpoints/servers.py` : champs ajoutés à `ServerOut/Create/Update`.
  ⚠️ Bug trouvé et corrigé en testant : `update_server()` exigeait
  `get_current_user` (JWT SIPV strict) alors que `list_servers()` acceptait déjà
  `get_current_user_or_service` (clé API ERPCRM) — le nouveau proxy PUT côté
  ERPCRM échouait donc systématiquement (502 "SIPV injoignable"). Harmonisé sur
  `get_current_user_or_service`, même pattern que le reste des endpoints proxy
  ERPCRM→SIPV déjà établis cette nuit (dids.py, ivr.py, routes.py).
- Côté ERPCRM : `sipv_client.update_server()`, nouveau `PUT /server/servers/{id}`
  (n'existait pas du tout avant — la page Serveur ne pouvait QUE lister, aucune
  édition possible jusqu'ici). `frontend/src/pages/Server.jsx` : nouvelle section
  "Canaux SIP (fournisseur)" avec 2 champs (IP entrante/sortante), sauvegarde au
  `onBlur`, avertissement explicite que rien n'est encore appliqué au réseau réel
  du serveur — champs de configuration/référence seulement, pas branchés à l'ACL
  (TASK-S050) ni à aucun binding FreeSWITCH pour l'instant.
Testé de bout en bout via le proxy ERPCRM (valeurs jetables 1.2.3.4/1.2.3.5,
retirées après validation) : PUT confirmé propagé jusqu'à SIPV, relecture
confirmée. Build frontend vérifié (`npm run build` OK).
Reste à faire : rien de prévu tant que l'utilisateur n'a pas les vraies IP de son
fournisseur — appliquer ces valeurs au binding réseau réel (external_sip_ip,
éventuellement l'ACL TASK-S050 si le fournisseur distingue aussi ses propres IP
entrante/sortante) sera une tâche séparée une fois les IP connues.
Fichiers : `sipv/backend/app/models/server.py`, `api/v1/endpoints/servers.py`,
`alembic/versions/0058_server_sip_channel_ips.py`,
`erpcrm/backend/app/core/sipv_client.py`, `api/v1/endpoints/server.py`,
`erpcrm/frontend/src/pages/Server.jsx`.

#### TASK-S048 [x] Bug critique — TenantDID jamais synchronisé vers InboundRoute (routage réel)
Découvert cette session (2026-08-07 nuit) en creusant TASK-S047. `_dialplan_public()`
(`xml_curl.py`, appelé par FreeSWITCH pour CHAQUE appel entrant réel) lit UNIQUEMENT
`InboundRoute` — jamais `TenantDID`. Or `sync.py::sync_did()` (appelé par ERPCRM à
chaque changement de destination d'un DID, chemin normal quotidien) n'écrivait QUE
dans `TenantDID`, malgré son propre docstring affirmant le contraire ("SIPV reste la
source réelle du routage d'appel" — faux, vérifié dans le code réel). Même lacune
dans `dids.py` (chemin SIPV natif). Concrètement : changer la destination d'un DID
depuis la fiche compagnie ERPCRM (ou l'admin SIPV) n'avait AUCUN effet sur un appel
entrant réel, sauf pour le seul DID de test (`15143222112`, TASK-S044) routé par un
script ponctuel qui touchait directement `InboundRoute` en contournant tout le reste.
Avec les vraies lignes SIP arrivées cette semaine, ce bug aurait cassé silencieusement
tout routage entrant configuré normalement.
Fait :
- `app/core/did_route_sync.py` (nouveau) : `sync_inbound_route_from_did(did, db)` —
  crée/met à jour/supprime l'`InboundRoute` miroir d'un `TenantDID` (retrouvée par
  `did_id`, avec fallback par `did_number` pour adopter une route legacy créée avant
  ce correctif sans lien `did_id`). Pas de destination ou DID inactif → route retirée
  (jamais de routage fantôme vers une ancienne destination).
- Appelé depuis `sync.py::sync_did()` (chemin ERPCRM, create + update) et
  `dids.py::create_did()/update_did()/delete_did()` (chemin SIPV natif) — les deux
  seuls points d'entrée qui modifient un DID.
- `routes.py` : `DEST_TYPES` (InboundRoute) était en retard sur `dids.py` — ajouté
  fax/conference/transfer/message pour cohérence d'affichage.
Testé de bout en bout via API (tenant test `t1001`, DID jetable `9995551234`, jamais
un vrai DID de production) : création d'un `TenantDID` avec `destination_type=message`
→ `InboundRoute` créée automatiquement et confirmée en base ; simulation d'un vrai
lookup dialplan FreeSWITCH (`POST /xml_curl` avec les champs exacts `Caller-Context`/
`Caller-Destination-Number` qu'envoie réellement FreeSWITCH) → XML de routage correct
retourné ; désactivation du DID → `InboundRoute` supprimée automatiquement. Données de
test entièrement nettoyées après validation.
⚠️ Reste à faire (hors scope de cette session, découvert en testant) : les
`InboundRoute` déjà en place pour de vrais DID configurés AVANT ce soir (s'il y en a,
au-delà du DID de test `15143222112`) n'ont pas été auditées une par une — à vérifier
avec l'utilisateur qu'aucune destination configurée récemment côté ERPCRM n'a été
silencieusement ignorée avant ce correctif.
Fichiers : `backend/app/core/did_route_sync.py` (nouveau),
`api/v1/endpoints/sync.py`, `api/v1/endpoints/dids.py`, `api/v1/endpoints/routes.py`.
Déployé sur le serveur réel (192.168.1.55), migration 0056 appliquée,
`sipv-backend`/`sipv-backend-tls` redémarrés, `/api/health` vérifié après coup.

#### TASK-S033 [x] MOH — Music on Hold (câblé pour le hold_music général ; queue mod_callcenter reste bloquée)
Demande de l'utilisateur (2026-08-07/08) : bibliothèque MOH gérée dans "Serveur"
(admin ERPCRM) pour voir/téléverser tous les fichiers ; page Compagnie pour voir/choisir
les MOH dédiées à ce tenant ; un fichier téléversé SANS compagnie assignée est "Global"
et apparaît comme option pour TOUTES les compagnies ; sélection multiple et ordonnée
par compagnie.
⚠️ Rappel du blocage découvert en creusant TASK-S047/S048 (toujours vrai, non résolu
ce soir, scope différent) : `Queue.music_on_hold` (mod_callcenter, musique d'attente
en file d'attente) reste un champ mort — `callcenter.conf.xml` n'est jamais généré
dynamiquement par `xml_curl.py`. CE QUI A ÉTÉ FAIT ce soir est différent et
indépendant : le `hold_music` général (musique jouée pendant un simple hold/transfert
d'appel, variable de canal FreeSWITCH standard), qui ne dépend PAS de mod_callcenter et
pouvait être câblé sans ce prérequis.
Fait :
- `models/moh.py` (nouveau) — `MohFile` (tenant_id FK nullable = global, name,
  filename, duration_seconds, is_active, created_at) + `TenantMohSelection`
  (tenant_id, moh_file_id, sort_order — sélection multiple ordonnée par tenant).
- `api/v1/endpoints/moh.py` (nouveau) — CRUD complet (upload multipart avec même
  conversion ffmpeg que prompts.py/voicemail.py : WAV PCM 8kHz mono + durée via
  ffprobe), `GET ""` (toutes, page Serveur), `GET /available/tenant/{id}` (globales +
  dédiées à ce tenant, page Compagnie), `PUT/GET /selection/tenant/{id}` (remplacement
  complet ordonné), `DELETE` (régénère les tenants affectés).
- `core/local_stream.py` (nouveau) — approche additive volontaire pour ne JAMAIS
  toucher au `local_stream.conf.xml` statique existant (5 flux par défaut déjà en
  place) : un seul ajout ponctuel `<X-PRE-PROCESS include data="../local_stream/*.xml">`
  fait lors du déploiement (voir ci-dessous), puis CE module écrit/réécrit un fragment
  `<include>` DISTINCT par tenant dans ce répertoire — jamais le fichier principal.
  Même pattern déjà utilisé pour les gateways de trunk (`sip_profiles/external/*.xml`).
  `regenerate_tenant_moh_stream()` : recopie les fichiers sélectionnés (ordre =
  sort_order) dans `sounds/sipv_moh/{account}/`, écrit `local_stream/moh_{account}.xml`,
  recharge `mod_local_stream` via `fs_cli`. Sélection vidée → fragment + dossier
  retirés (le tenant retombe sur le flux "default" du profil SIP, comportement standard
  FreeSWITCH). Best-effort total (try/except + log), ne bloque jamais l'appelant.
- `xml_curl.py::_user_xml()` — `hold_music_var` : si un fragment existe pour ce tenant
  (vérif filesystem, pas de requête DB — appelé à chaque REGISTER), règle la variable
  de canal `hold_music=local_stream://moh_{account}` dans le directory XML.
- `main.py` : `include_router(moh.router, prefix="/api/v1/moh")`.
- Déploiement serveur réel (192.168.1.55, hors git) : création de
  `conf/local_stream/` et `sounds/sipv_moh/` (owner `sipv:sipv` — le service tourne
  sous cet utilisateur, pas `freeswitch`) ; UNE modification ponctuelle de
  `autoload_configs/local_stream.conf.xml` (ajout de la ligne `X-PRE-PROCESS include`
  juste après `<configuration>`, backup `.bak_20260808` avant coup) ; les 5
  `<directory>` par défaut jamais touchés (deux d'entre eux ont des chemins cassés
  préexistants, sans lien avec ce soir).
Bug corrigé pendant l'implémentation : `moh_stream_name()` produisait
`"moh_t{account_number}"` où `account_number` a déjà "t" en préfixe (ex: "t1001"),
donnant "moh_tt1001" — corrigé en `f"moh_{account_number}"`.
Bug corrigé après premier test bout en bout : `GET /api/v1/moh` (liste globale, page
Serveur) utilisait `get_current_user` (JWT SIPV strict) au lieu de
`get_current_user_or_service` — ERPCRM n'a pas de compte SIPV, appelle toujours via
X-Api-Key, donc cet appel échouait TOUJOURS en 401 malgré tous les autres endpoints MOH
correctement câblés avec `get_current_user_or_service`. Même famille de bug que le fix
`update_server` de TASK-S054. Redéployé + `sipv-backend-tls` (le service qui sert
réellement le trafic ERPCRM←→SIPV, distinct de `sipv-backend`) redémarré — le premier
redémarrage n'avait ciblé QUE `sipv-backend`, oubli initial corrigé dans la foulée.
Testé en direct sur le serveur réel (tenant test `t1001`) : upload d'un WAV de test
global, apparu dans liste globale + liste "disponible" du tenant, sélection appliquée,
fragment `local_stream/moh_t1001.xml` + dossier `sounds/sipv_moh/t1001/` confirmés créés
avec le contenu attendu, `reload mod_local_stream` propre (aucune nouvelle erreur).
Sélection vidée puis fichier supprimé : fragment + dossier retirés automatiquement,
fichier uploadé retiré. Rien laissé en place après le test.
Frontend ERPCRM (pas SIPV cette fois — décision explicite de l'utilisateur, contrairement
à TASK-S046/Phrases) : voir TASK-021.x dans TASKERPCRM.md (page Serveur + fiche
Compagnie).
Reste bloqué (hors scope, prérequis plus large, voir avertissement ci-dessus) : MOH de
file d'attente (mod_callcenter/`Queue.music_on_hold`) — nécessite la génération
dynamique de `callcenter.conf.xml`, jamais entamée.
Migration : `0059_moh.py`.
Fichiers : `backend/app/models/moh.py` (nouveau), `models/__init__.py`,
`core/local_stream.py` (nouveau), `api/v1/endpoints/moh.py` (nouveau),
`api/v1/endpoints/xml_curl.py`, `main.py`, `alembic/versions/0059_moh.py` (nouveau).

##### TASK-S033.1 [x] Écoute par appel poste + ordre liste/aléatoire par tenant

Voir TASKERPCRM.md TASK-028.4 pour le détail complet côté ERPCRM (demande
utilisateur, UI). Côté SIPV :
- `POST /v1/moh/{id}/call` (meme principe que `AudioPrompt.call`/TASK-S055,
  `esl.originate_app` direct). ⚠️ Bug trouvé en testant en direct :
  lecture directe depuis `uploads/moh_files/` (sous `/home/sipv/`, 750)
  échouait "Permission denied" pour l'utilisateur `freeswitch` --
  traversée du dossier parent bloquée, pas juste les droits du fichier
  lui-même (même cause que `PROMPT_CACHE_DIR`, TASK-S055). Corrigé :
  copie vers `/usr/local/freeswitch/conf/moh_call_cache/` (créé
  manuellement, `chown sipv:sipv`, `755`, pas persistant via
  code/migration) avant de jouer.
- `Tenant.moh_shuffle` (nouveau, migration `0060`, défaut `true` =
  comportement historique inchangé) — `regenerate_tenant_moh_stream` lit
  ce champ au lieu de `shuffle=true` codé en dur. Mise à jour via
  `PUT /tenants/{id}` (générique, `setattr`), déclenche la régénération du
  flux `local_stream` immédiatement.
- 4 pistes stock FreeSWITCH (`sounds/music/8000/*.wav`, déjà 8kHz)
  importées comme `MohFile` globaux actifs par défaut (script ponctuel,
  pas une migration) : Bach, Ponce, Granados, Albéniz.

Migration : `0060_tenant_moh_shuffle.py`.
Fichiers : `models/tenant.py`, `api/v1/endpoints/{tenants,moh}.py`,
`core/local_stream.py`, `alembic/versions/0060_tenant_moh_shuffle.py`.

##### TASK-S033.2 [x] 0.5s de silence avant le début du MOH ("ça commence trop raide")

`hold_music` passe de `local_stream://{stream}` à
`file_string://silence_stream://500!local_stream://{stream}` --
`file_string://` (verifie dans le source FreeSWITCH,
`mod_dptools.c::file_string_file_open`) chaine plusieurs sources avec `!`
en une seule lecture ; `silence_stream://500` genere 500ms de silence
(mod_tone_stream). Rejoue a CHAQUE Hold (nouveau `playback()` a chaque
fois, confirme dans les logs plus tot dans cette session) meme si
`local_stream` est un flux partage continu -- le silence, lui, n'est pas
partagé, donc l'effet "pause avant le début" fonctionne a chaque hold,
pas juste au tout premier appel.
Fichiers : `api/v1/endpoints/xml_curl.py` (`_user_xml`, `hold_music_var`).

##### TASK-S033.3 [ ] Même délai pour les Phrases IVR -- configurable, 0.5s par défaut (PAS COMMENCÉ, prochaine conversation)

Demande de l'utilisateur (2026-08-12) : même principe que TASK-S033.2 mais
pour les Phrases IVR (`AudioPrompt`, TASK-S046/TASK-S055) -- un délai de
silence AVANT la lecture d'une phrase choisie dans un IVR, 0.5s par défaut,
mais CONFIGURABLE (pas fixe comme pour le MOH). Explicitement reporté à une
prochaine conversation par l'utilisateur -- ne pas commencer sans nouveau
GO. Probablement : nouveau champ sur `AudioPrompt` ou sur le point
d'utilisation dans l'IVR (`IVROption`?), à clarifier au démarrage de cette
tâche (où exactement le délai doit être réglable -- par phrase ? par usage
dans un IVR précis ?). Même mécanisme technique que S033.2
(`file_string://silence_stream://{ms}!...`) réutilisable.

#### TASK-S046 [x] Bibliothèque de phrases/annonces réutilisables (Prompts)
Demande de l'utilisateur (2026-08-07, tard le soir — terminologie "phrases" empruntée
à ScopServ) : un enregistrement uploadé une seule fois et réutilisable à plusieurs
endroits — attribuable à un IVR (greeting), ou joué directement comme destination
d'un DID/route entrante, sans dupliquer le fichier par usage. Emplacement UI confirmé
par l'utilisateur : nouvel onglet "Phrases" dans `TenantDetail.jsx` (admin SIPV).
Fait :
- `models/prompt.py` (nouveau) — `AudioPrompt` (tenant_id FK CASCADE, name,
  filename, duration_seconds nullable, is_active, created_at).
- `api/v1/endpoints/prompts.py` (nouveau) — upload multipart (name + file, même
  conversion ffmpeg que `voicemail.py::upload_greeting` : WAV PCM 8kHz mono, + durée
  calculée via `ffprobe`), GET liste par tenant, GET fichier, PUT (rename/actif),
  DELETE. `get_current_user_or_service` (accepte X-Api-Key ERPCRM comme les autres
  endpoints proxy) — pas de compte SIPV requis pour un futur appel depuis ERPCRM.
- **Suppression bloquée si référencée** (décision prise sans redemander : cohérent
  avec la loi "toujours pouvoir rediter"/robustesse déjà établie sur ce projet) —
  `_prompt_usages()` vérifie IVR.greeting_prompt_id, TenantDID (destination et
  after_message_destination de type "message"), InboundRoute — retourne la liste
  lisible des usages dans le message d'erreur 400 plutôt que de laisser une
  référence orpheline.
- `main.py` : `include_router(prompts.router, prefix="/api/v1/prompts")`.
- Frontend (`frontend/src/pages/TenantDetail.jsx`) : nouvel onglet "Phrases" — champ
  nom + input fichier + bouton téléverser, tableau (nom/durée/statut cliquable pour
  actif-inactif/supprimer). `npm run build` vérifié OK.
Migration : `0056_audio_prompts.py` (table `audio_prompts`, voir aussi TASK-S047).
Testé en direct sur le serveur réel (tenant test `t1001`) : upload d'un WAV de test
(conversion ffmpeg + durée détectée à 2s confirmées), liste, suppression bloquée avec
message listant les usages, suppression réussie une fois libérée. Fichier + entrée DB
de test retirés après validation.
Reste à faire (hors scope ce soir) : le frontend admin SIPV (`dist/`) n'est PAS servi
par un service sur le serveur (nginx ne sert que l'ancien FusionPBX abandonné) — même
constat que TASK-S036/S018 déjà documenté, pas une régression de cette tâche. Pour
voir l'onglet "Phrases" il faut lancer le frontend en dev (`npm run dev`) comme pour
le reste de l'admin SIPV.
Fichiers : `backend/app/models/prompt.py` (nouveau), `models/__init__.py`,
`api/v1/endpoints/prompts.py` (nouveau), `main.py`,
`alembic/versions/0056_audio_prompts.py` (nouveau),
`frontend/src/pages/TenantDetail.jsx`.

#### TASK-S047 [x] Câblage réel des phrases dans IVR (greeting) + destination DID/route "message"
Dépend de : TASK-S046 ✓, TASK-S048 ✓ (sans le fix S048, ce câblage n'aurait jamais
été atteignable par un DID configuré normalement depuis ERPCRM).
Décisions confirmées par l'utilisateur avant implémentation : page dans TenantDetail
(fait, voir TASK-S046) ; raccroché automatique PAR DÉFAUT après la lecture du
message ; possibilité d'"Ajouter une destination" pour chaîner vers une 2e
destination après le message (au lieu de raccrocher).
Fait :
- `models/sip.py` (`TenantDID`) et `models/dialplan.py` (`InboundRoute`) : nouveaux
  champs `after_message_destination_type`/`after_message_destination` (nullable,
  significatifs seulement quand `destination_type == "message"`).
- `models/ivr.py` (`IVR`) : nouveau champ `greeting_prompt_id` (FK `audio_prompts.id`,
  `ON DELETE SET NULL`) — prioritaire sur `greeting_text` (texte libre/TTS) quand
  renseigné, sans rien casser pour les IVR existants (fallback inchangé).
- `api/v1/endpoints/xml_curl.py` :
  - `_inbound_actions()` renommée en délégation vers `_inbound_actions_for(dest_type,
    dest, tenant, db, after_type, after_dest)` — même logique extension/ivr/queue/
    voicemail/hangup qu'avant (aucun changement de comportement), + nouveau cas
    `dest_type == "message"` : `answer` + `playback` du fichier du prompt, puis soit
    `hangup NORMAL_CLEARING` (défaut), soit récursion dans
    `_inbound_actions_for(after_type, after_dest, ...)` si `after_type` est renseigné
    — un seul niveau de chaînage autorisé (`after_type == "message"` explicitement
    ignoré pour ne jamais boucler).
  - `_config_ivr()` : precharge les `AudioPrompt` référencés en un seul aller-retour
    DB, utilise le chemin du fichier comme `greet-long`/`greet-short` quand
    `greeting_prompt_id` est renseigné et le prompt actif, sinon comportement
    inchangé (`greeting_text` ou fichier par défaut).
- `api/v1/endpoints/ivr.py` : `greeting_prompt_id` ajouté à `IVROut`/`IVRCreate`, +
  nouveau `PUT /ivr/{ivr_id}` (`IVRUpdate`) — n'existait pas avant (seuls list/create/
  delete existaient), nécessaire pour assigner un greeting après coup.
- `api/v1/endpoints/dids.py`/`sync.py`/`routes.py` : `after_message_destination_type`/
  `after_message_destination` exposés sur `DIDOut/Create/Update`,
  `ERPCRMDidSync`, `InboundRouteOut/Create/Update`.
Testé de bout en bout sur le serveur réel (simulations des vraies requêtes que
FreeSWITCH envoie, pas juste des appels API) :
- `message` sans chaînage → XML confirmé : `answer` + `playback` + `hangup
  NORMAL_CLEARING`.
- `message` avec `after_message_destination_type=extension` → XML confirmé :
  `playback` puis `bridge user/t1001-100@sipv` (pas de hangup).
- `greeting_prompt_id` sur un IVR → `ivr.conf` généré confirmé avec `greet-long`/
  `greet-short` pointant sur le fichier du prompt.
- Suppression d'un prompt encore utilisé (greeting IVR + destination DID) → bloquée
  avec le détail des deux usages (voir TASK-S046).
Écart vs plan initial : les OPTIONS d'IVR par chiffre (0-9/*/#, `IVROption.
destination_type`) n'ont PAS reçu de type "message" — volontairement laissé de côté.
`_ivr_option_action()` génère un seul `menu-exec-app <app> <args>` par option
(mod_dptools FreeSWITCH n'exécute qu'UNE app par entrée) ; "jouer un message PUIS
raccrocher/continuer" dans ce contexte précis nécessiterait de transférer l'appel
vers une extension de dialplan synthétique dédiée — plus risqué et non testable
sans un vrai appel (pas de softphone disponible dans cette session). Seuls les DEUX
usages explicitement décrits par l'utilisateur ce soir sont couverts : greeting
d'IVR, et destination directe d'un DID/route entrante. Documenté comme TASK-S047.1
si un jour demandé.
⚠️ Reste à faire côté ERPCRM (pas fait ce soir, voir TASKERPCRM.md) : le sélecteur
"Message enregistré" existe déjà dans `CompanyDetail.jsx`
(`DID_DESTINATION_TYPES`), mais `destinationSelectOptions()` ne connaît pas encore
les prompts d'un tenant — aujourd'hui il faut coller l'UUID du prompt à la main dans
le champ destination (fonctionnel mais peu ergonomique), et il n'y a aucun contrôle
"Ajouter une destination" pour le chaînage après-message. Backend 100% prêt
(`GET /prompts/tenant/{id}` accepte déjà X-Api-Key ERPCRM) — reste juste le proxy
ERPCRM + la liste déroulante + le bouton de chaînage côté frontend.
Migration : `0056_audio_prompts.py` (mêmes fichiers que TASK-S046, une seule
migration pour les deux tâches).
Fichiers : `backend/app/models/sip.py`, `models/dialplan.py`, `models/ivr.py`,
`api/v1/endpoints/xml_curl.py`, `api/v1/endpoints/ivr.py`, `api/v1/endpoints/dids.py`,
`api/v1/endpoints/sync.py`, `api/v1/endpoints/routes.py`.

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
| TASK-S032  | billing link | ✓ SIPV → ERPCRM billing triggers (service créé/retiré → lignes facturation + prorata)   |

#### TASK-S032 [x] Billing triggers SIPV → ERPCRM
Demande explicite de l'utilisateur (2026-08-08) : facturation automatique
obligatoire ("je veux une facturation automatique pas le choix pour éviter que
je donne des services gratuits"), avec retrait au prorata de la date de
facturation. Design confirmé par l'utilisateur : une seule récurrence par
compagnie (toutes les lignes de service ensemble), date de départ + fréquence
choisies à l'activation du tenant SIPV, article "Prorata" dédié pour les
crédits de retrait, nouvel onglet "Récurrence" côté ERPCRM.

Protection double-facturation (clients ScopServ actuels) : vérifié en direct
qu'un seul tenant existe dans SIPV (`t1001` = Simple IP inc., aucun autre
client n'a encore de tenant) — la protection naturelle est que `sipv_enabled`
non coché = aucun tenant = rien à facturer. Confirmé par l'utilisateur comme
suffisant (pas d'interrupteur "facturation active" séparé demandé).

Fait côté SIPV :
- `app/core/erpcrm_client.py` : `send_billing_event()` — appel best-effort vers
  `POST {ERPCRM_API_URL}/api/v1/billing/sipv-event` (X-Api-Key SIPV_API_KEY,
  même TLS inter-serveurs déjà en place TASK-039).
- `api/v1/endpoints/extensions.py` : `create_extension`/`delete_extension`
  envoient `extension_added`/`extension_removed` (service_ref = id du poste,
  stable pour retrouver la ligne au retrait) — best-effort, ne bloque jamais
  la création/suppression réelle du poste si ERPCRM est injoignable.
- `api/v1/endpoints/sync.py::sync_did()` : `did_added` envoyé UNIQUEMENT sur
  `action == "created"` (pas update/adopted) -- c'est le chemin RÉEL de
  création des DID en pratique (ERPCRM maître, TASK-S010.5), contrairement à
  `dids.py::create_did()` qui est le chemin natif SIPV rarement emprunté pour
  de vrais DID (câbler seulement ce dernier aurait été un câblage décoratif,
  même piège que TASK-S047/S048/S051 -- vérifié explicitement avant d'écrire
  le code, pas après).
- `api/v1/endpoints/dids.py::delete_did()` : `did_removed` — chemin unique de
  suppression peu importe l'appelant (ERPCRM proxy ou admin SIPV natif), donc
  aucun risque de double notification contrairement à la création.
Testé en direct (pas juste simulé) : appel réel `erpcrm_client.send_billing_event()`
depuis le serveur SIPV vers ERPCRM (vraie connexion réseau/TLS) — ligne confirmée
créée côté ERPCRM, puis retrait confirmé, aucune trace résiduelle après nettoyage.
Voir TASKERPCRM.md TASK-021 pour le détail complet côté ERPCRM (modèles,
calcul de prorata, onglet Récurrence, tests de bout en bout).
Fichiers : `backend/app/core/erpcrm_client.py`, `api/v1/endpoints/extensions.py`,
`api/v1/endpoints/dids.py`, `api/v1/endpoints/sync.py`.

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

### TASK-023.17 [x] Boutons/touches programmables — éditeur en LISTE (découplé de la photo)
Demande de l'utilisateur : ne pas attendre la photo du GXP2135 (S011.3 bloquée) pour
pouvoir gérer les boutons programmables — un éditeur en liste (pas visuel) couvre le
même besoin de données dès maintenant.

Fait (migration `0038_phone_buttons`) : nouvelle table `phone_buttons` rattachée à
`ProvisionedPhone` (pas à `PhoneModel` — les valeurs assignées sont par APPAREIL
physique, cohérent avec la décision déjà prise dans S011.2 "la config reste attachée
au poste logique/à l'appareil, pas dupliquée"). Champs : `position`, `page`,
`button_type` (ligne/BLF/composition rapide/parc/récupération de parc/messagerie/
transfert/intercom/paging/DND/renvoi/file/connexion-déconnexion-pause agent/pickup
group/code de fonction/porte/répertoire), `label`, `value`, `destination`,
`sip_account_index` (quel compte SIP du téléphone), `client_editable`,
`locked_by_simpleip`. CRUD complet : `GET/POST /provisioning/{phone_id}/buttons`,
`PUT/DELETE /provisioning/buttons/{button_id}`.

Testé en direct : téléphone de test créé, bouton BLF créé (poste 100), listé,
modifié (type + client_editable), supprimé ; téléphone de test supprimé ensuite —
suppression en cascade des boutons confirmée (0 lignes `phone_buttons` après). Les 3
postes de test restent `Registered`.
Reste (hors scope ici, c'est explicitement S011.3) : l'image cliquable elle-même
attend toujours la photo. Cette table est réutilisable telle quelle par S011.3 quand
la photo arrivera (mêmes colonnes, juste une UI différente par-dessus).
Fichiers : sipv/backend/app/models/provisioning.py, models/__init__.py,
api/v1/endpoints/provisioning.py, alembic/versions/0038_phone_buttons.py.

### TASK-023.18 [x] Catalogue PhoneModel Grandstream (65 modèles)
Demande de l'utilisateur : "on peut commencer avec la game de grandstream, les
modèles que tu vois dans le fichier config" -- référence P-code déjà déposée dans
`/home/simpleip/GrandStream/Template_Config_Pcode/config-template/`.

Fait (migration `0039_seed_grandstream`, idempotente -- guard sur `brand=
'Grandstream'`) : 65 fichiers `.txt` parsés, dédupliqués par famille (garde la
version firmware la plus récente par famille, ex. `gxp2130_40_60_70_35_config_
1.0.11.106.txt` → un seul modèle `"GXP2130/40/60/70/35"`, pas éclaté en 5 lignes --
suit le regroupement déjà fait par le fabricant dans le nom du fichier plutôt que
de deviner les SKU exacts). `device_type` classé par préfixe de famille connu
(GXP/GRP/GHP/GAC/GVC/DP7xx/WP8xx = téléphone ; HT5xx/7xx/8xx/GXW4xxx = ATA ;
GDS37xx/GSC35xx/GXV33xx/GXV3500 = intercom/porte ; GS Wave = softphone). Fichiers
non pertinents exclus (`gxp_config` générique trop ancien, `surveilliance_general`
= caméra pas un téléphone, artefacts `new`/`2.txt`).

Testé en direct : 65 modèles créés via l'API (pas d'insertion SQL directe pour le
seed initial -- passé par `POST /provisioning/models` comme un usage normal),
vérifié via `GET /provisioning/models` (65 lignes actives). Migration ensuite
appliquée sur la même DB pour vérifier l'idempotence : guard a correctement empêché
toute duplication (comptage inchangé, hors 1 modèle de test résiduel désactivé de
TASK-023.13). Les 3 postes de test restent `Registered`.
Fichiers : sipv/backend/alembic/versions/0039_seed_grandstream.py.

### TASK-023.19 [~] Accès proxy ERPCRM pour modèles/appareils/boutons
Préparation nécessaire côté SIPV avant l'UI ERPCRM (fiche contact -- attribution
appareil + éditeur de boutons) : les endpoints `/provisioning/models` (liste),
`/provisioning/tenant/{id}` (liste/création téléphone), `/provisioning/{id}` (PUT),
et les 4 endpoints boutons n'acceptaient QUE `get_current_user` (JWT humain) --
ERPCRM (proxy serveur-à-serveur, clé API) ne pouvait pas les appeler. Basculés vers
`get_current_user_or_service` (même pattern que extensions.py). Nouvel endpoint
`GET /provisioning/by-extension/{extension_id}` (retourne le téléphone attribué à
ce poste, ou `null` si aucun -- pas une erreur) pour que la fiche contact ERPCRM
puisse retrouver l'appareil sans connaître son ID directement.

Testé en direct : `GET /provisioning/by-extension/{id}` appelé avec `X-Api-Key`
(pas de JWT) sur un poste sans appareil attribué -- `null` retourné correctement,
pas de 401/403. Les 3 postes de test restent `Registered`.
Fichiers : sipv/backend/app/api/v1/endpoints/provisioning.py.

### TASK-023.20 [x] Accès proxy ERPCRM pour les groupes d'appel (ring groups)
Même préparation que TASK-023.19 mais pour les 7 endpoints `ring-groups` (list/
create/update/delete + membres) — basculés vers `get_current_user_or_service`,
`created_by=user.email if user else "erpcrm-proxy"` (même repli que TASK-023.4).

Testé en direct : `GET /ivr/ring-groups/tenant/{id}` appelé avec `X-Api-Key` seul
(pas de JWT) -- liste vide retournée correctement, pas de 401/403. Les 3 postes de
test restent `Registered`.
Fichiers : sipv/backend/app/api/v1/endpoints/ivr.py.

### TASK-023.23 [~] Paging groups (bidirectionnel/unidirectionnel, multicast)
Demande de l'utilisateur : 3e section séparée (ring group ✓, pickup ✓, paging) --
"dans grandstream ucm on peut faire des page bidirectionnelle et unidirectionnelle,
j'aimerais ça l'avoir aussi".

Fait (migration `0040_paging_groups`) : nouveau modèle `PagingGroup` (extension pour
déclencher, `mode` unidirectional/bidirectional, `multicast_address`/`multicast_port`)
+ `PagingGroupMember` (extension_id, `can_send`, `can_receive`). CRUD complet
(`/ivr/paging-groups/...`, miroir exact du pattern RingGroup).

Câblage dialplan (`_paging_dialplan_entries()`) : diffusion simultanée
(`bridge` avec `:_:`) vers tous les membres `can_receive`, préfixée du même
`{sip_h_Call-Info=<sip:intercom>;answer-after=0}` déjà validé pour l'intercom
(S023.11) -- auto-answer sur chaque récepteur.

⚠️ Vérifié AVANT de coder plutôt que deviné : `page` (application FreeSWITCH dédiée
au paging one-way) N'EST PAS disponible sur ce build (`show application` -- 0
résultat pour `page`, `bridge` confirmé présent) -- donc PAS utilisée, `bridge`
employé à la place pour les deux modes.
⚠️ [~] : `mode="unidirectional"` ne coupe PAS réellement l'audio du récepteur vers
l'émetteur dans cette implémentation -- aucun mécanisme fiable trouvé/vérifié pour
ça avec les outils disponibles sur ce build. Les deux modes se comportent donc
identiquement côté FreeSWITCH pour l'instant (diffusion auto-répondue) ; documenté
honnêtement plutôt que de prétendre un one-way qui ne l'est pas réellement.
`multicast_address`/`multicast_port` sont des données de PROVISIONING téléphone
(P-codes, TASK-S011.4 pas commencée) -- le vrai paging multicast Grandstream se
fait téléphone-à-téléphone sur le LAN, hors du chemin média de FreeSWITCH ; stockées
pour cet usage futur, pas encore consommées.

Testé en direct : groupe de test créé (extension 160, mode unidirectional, adresse
multicast de test), membre ajouté (poste réel t1001-101, can_receive seulement) --
XML dialplan généré vérifié (`{sip_h_Call-Info=...}user/t1001-101@t1001` présent au
bon endroit). Cycle CRUD complet testé (create/update mode/delete membre/delete
groupe). SIPV confirmé propre après (0 lignes dans les deux tables), les 3 postes
de test restent `Registered`.
Fichiers : sipv/backend/app/models/ivr.py, models/__init__.py,
api/v1/endpoints/xml_curl.py, api/v1/endpoints/ivr.py,
alembic/versions/0040_paging_groups.py.

### TASK-023.25 [x] Templates de configuration de boutons (sauvegarder/appliquer)
Dernier morceau de la demande boutons (TASK-023.17) : "je vais pouvoir créer une
config de bouton et le mettre en template pour l'activer sur d'autres".

Fait (migration `0041_button_templates`) : `PhoneButtonTemplate` (nom + tenant) +
`PhoneButtonTemplateItem` (mêmes champs qu'un `PhoneButton`, sans rattachement à un
appareil précis). Endpoints :
- `GET /provisioning/button-templates/tenant/{tenant_id}` (liste)
- `DELETE /provisioning/button-templates/{template_id}`
- `POST /provisioning/{phone_id}/save-as-template` -- copie les boutons ACTUELS
  d'un téléphone dans un nouveau template nommé.
- `POST /provisioning/button-templates/{template_id}/apply/{phone_id}` -- REMPLACE
  les boutons existants de l'appareil cible par ceux du template (sémantique
  "appliquer" simple et prévisible, pas une fusion qui laisserait des boutons
  orphelins de l'ancienne config).

Testé en direct de bout en bout : 2 téléphones de test créés, 2 boutons ajoutés au
premier (BLF poste 100, composition rapide), sauvegardé comme template "Standard
Reception", appliqué au deuxième téléphone -- les 2 boutons copiés exactement
(mêmes valeurs, nouveaux IDs, `provisioned_phone_id` correctement réassigné).
Template + les 2 téléphones supprimés après coup (0 ligne `phone_button_templates`/
`phone_buttons` résiduelle). Les 3 postes de test restent `Registered`.
Fichiers : sipv/backend/app/models/provisioning.py, models/__init__.py,
api/v1/endpoints/provisioning.py, alembic/versions/0041_button_templates.py.

### TASK-S011.4 [~] Auto-provisioning Grandstream (fichier cfg<MAC>.xml, zero-touch)
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

**Fait le 2026-08-02** : premier vrai `config_template` GXP2135 écrit (Jinja2, notre
propre fichier — jamais de valeur copiée du fichier ScopServ réel fourni par
l'utilisateur comme référence structurelle, ni de la doc officielle Grandstream,
seulement les noms/positions de P-codes). Croisé le fichier ScopServ réel
(`/home/simpleip/Scopserv/cfg000b82bc987e.xml`, poste confirmé fonctionnel par
l'utilisateur) contre la doc officielle `gxp2130_40_60_70_35_config_1.0.11.106.txt`
pour valider chaque P-code avant de l'utiliser.
- Catalogue `PhoneModel` séparé : la ligne combinée "GXP2130/40/60/70/35" devient 5
  lignes individuelles (GXP2135 garde le même id — renommage, pas de recréation —
  pour ne pas casser un `ProvisionedPhone` déjà provisionné dessus). GXP2130/2140/
  2160/2170 créés vides (`config_template=NULL`), prêts pour plus tard.
- `get_phone_config` (endpoint existant) étendu : eager-load `phone.buttons` +
  `extension.tenant.server`, construit le contexte Jinja2 complet (compte SIP,
  transport, protocole/serveur de provisioning, options fusionnées).
- **Bug trouvé et corrigé pendant le test réel** : `extension.password` est stocké
  chiffré (Fernet, même convention que `xml_curl.py`) — le premier jet du template
  l'exposait tel quel (`{{ extension.password }}`), ce qui aurait envoyé un poste
  physique avec un mot de passe SIP illisible. Corrigé : déchiffré dans le contexte
  (`ext_password`, via le `_decrypt` déjà existant dans `provisioning.py`) avant le
  rendu. Trouvé par un test réel contre un poste de test (`Test Trois`), pas par
  relecture — leçon : toujours faire un rendu réel avant de considérer un template fini.
- Bloc touches programmables (P238xx, BLF/speed-dial/pickup) : réutilise
  `PhoneButton` existant (`button_type`/`label`/`value`/`sip_account_index`), aucune
  nouvelle table. **Ambiguïté résolue empiriquement** : la doc officielle étiquette
  la légende de ce bloc "Dynamic VPK" (0-26, où 1=BLF), mais le fichier ScopServ réel
  et fonctionnel utilise en pratique la légende "Fixed VPK" (-1 à 36, où 11=BLF,
  10=Speed Dial) — confirmé par test direct (rendu affiche bien `P23800=11` pour un
  bouton BLF réel). La doc semble mal étiquetée au-delà du 6e VPK ; le mapping
  `BUTTON_TYPE_TO_GS_MODE` dans `provisioning.py` suit le fichier réel, pas la doc.
- Testé de bout en bout contre les 2 postes de test actifs (`curl .../config`),
  avec et sans bouton BLF configuré — rendu XML complet vérifié à l'œil.
- **Reste à faire** (non touché aujourd'hui, hors demande) : le déclenchement
  "premier démarrage zero-touch" (DHCP option 66 vs configuration manuelle unique
  de `P237`) — question posée dans la version précédente de cette entrée, toujours
  sans réponse, pas nécessaire pour les tests actuels (postes déjà configurés une
  fois manuellement).
Fichiers : sipv/backend/app/api/v1/endpoints/provisioning.py, app/models/tenant.py,
alembic/versions/0045_gxp2135_provisioning.py.

### TASK-S011.5 [x] Catalogue d'options téléphonie — défaut compagnie + override poste
Demande de l'utilisateur (2026-08-02) : reproduire le concept "Options" de l'UCM
Grandstream (catalogue de réglages, seuls ceux ajoutés explicitement apparaissent —
page propre par défaut) sur 2 niveaux : Compagnie (défaut global) et Contact
(personnalisation qui écrase le défaut compagnie pour ce poste précis seulement).
- `Tenant.phone_option_defaults` (JSON, nullable) — défauts niveau compagnie.
- `ProvisionedPhone.extra_config` (JSON, existait déjà) — override niveau poste,
  réutilisé tel quel plutôt que d'ajouter un nouveau champ.
- Fusion dans `get_phone_config` : défaut système (`PHONE_OPTION_SYSTEM_DEFAULTS`,
  codé en dur dans `provisioning.py`) → `Tenant.phone_option_defaults` → `Phone
  Provisioned.extra_config`, le plus spécifique gagne (même esprit que
  `resolve_setting()`, mais sur un dict libre plutôt que des colonnes nommées).
- Catalogue volontairement minimal pour l'instant (une seule option : langue du
  poste, P1362) — extensible plus tard sans migration puisque tout passe par un
  dict JSON, catalogue affiché côté ERPCRM (`ref_data.py`).
- `GET /{tenant_id}` et `PUT /{tenant_id}` (tenants.py) changés de `get_current_user`
  à `get_current_user_or_service` pour qu'ERPCRM puisse les appeler en proxy
  (X-Api-Key) — même pattern déjà utilisé ailleurs, aucun autre endpoint tenant touché.
- Testé de bout en bout : défaut compagnie seul (P1362=fr rendu), override poste
  seul gagnant sur le défaut compagnie (P1362=auto malgré compagnie=fr), puis
  remis à vide après le test (aucune donnée réelle laissée modifiée).
Fichiers : sipv/backend/app/models/tenant.py, api/v1/endpoints/tenants.py,
api/v1/endpoints/provisioning.py, alembic/versions/0045_gxp2135_provisioning.py.

### TASK-023.13 [x] PhoneModel.device_type (téléphone/ATA/softphone/intercom)
Champ manquant confirmé en lisant le modèle (migration `0036_phone_device_type`,
défaut `"telephone"`). Testé en direct : modèle de test créé avec `device_type=
"ata"`, relu correctement, désactivé après coup (`is_active=false` -- pas de DELETE
sur `/provisioning/models`, seulement GET/POST/PUT, comportement pré-existant non
touché ici). Les 3 postes de test restent `Registered`.
Fichiers : sipv/backend/app/models/provisioning.py, api/v1/endpoints/provisioning.py,
alembic/versions/0036_phone_device_type.py.

### TASK-023.14 [x] Identification : langue d'affichage, fuseau horaire, nom "autre"
Migration `0037_ext_identification` : `display_language` (défaut `"fr"`, langue de
l'écran du téléphone -- distinct de `VoicemailBox.language`), `timezone` (nullable,
défaut projet America/Montreal si absent, pas de niveau d'héritage compagnie ajouté
ici -- champ d'affichage simple, pas de logique métier dessus), `name_override`.

`name_override` résout la demande "nom du poste même que le contact, checkbox pour
autre" : par défaut (`false`), `sync.py::erpcrm_event` (action `contact_name_changed`,
TASK-S022) met à jour `SIPExtension.name` EN PLUS de `caller_id_name` quand le
contact ERPCRM lié change de nom ; si `name_override=true`, `name` reste protégé
(saisi manuellement) mais `caller_id_name` continue de suivre le contact (les deux
notions restent indépendantes).
⚠️ Limite pré-existante non résolue ici (déjà notée dans TASK-018 TASKERPCRM.md) :
rien côté ERPCRM n'appelle encore `POST /sync/erpcrm-event` quand un contact change
de nom -- le mécanisme de sync existe et fonctionne (testé ci-dessous en appelant
l'endpoint directement), mais n'est pas encore déclenché automatiquement à la
source. Hors scope de cette tâche (identification du poste), pas inventé pour
combler ce gap.

Testé en direct sur t1001-101 (contact lié "Test Deux") : appel direct de
`/sync/erpcrm-event` avec `name_override=false` -> `name` ET `caller_id_name` mis à
jour ("Nouveau Nom") ; puis `name_override=true` + nouvel événement -> `name` reste
protégé ("Nouveau Nom" inchangé) MAIS `caller_id_name` suit quand même ("Autre
Personne"). Tout remis à l'état initial ("Test Deux") après vérification. Les 3
postes de test restent `Registered`.
Fichiers : sipv/backend/app/models/sip.py, api/v1/endpoints/sync.py,
api/v1/endpoints/extensions.py, alembic/versions/0037_ext_identification.py.

### TASK-023.15 [x] Préfixe d'interception *8 réellement câblé
`pickup_group`/`can_intercept_calls` existaient (S007.2) mais aucun préfixe de code
feature ne les utilisait -- juste des champs stockés, non actionnables.

Fait : `_pickup_dialplan_entries()` -- résolu au moment de la génération XML (pas de
cache xml_curl côté FreeSWITCH, chaque tentative de `*8` redéclenche un vrai lookup) :
interroge ESL (`show channels as json`) pour trouver un canal `RINGING`/`EARLY` dont
le callee appartient au MÊME `pickup_group` que le poste appelant, puis émet
`<action application="intercept" data="{uuid réel}">`. Rien n'est émis si l'appelant
n'a pas de `pickup_group` / n'a pas `can_intercept_calls` -- `*8` tombe alors sur le
catchall (486) comme avant, aucune régression pour les postes qui n'ont pas cette
fonctionnalité configurée.

Testé en direct avec un VRAI appel (pas juste structurel) : `pickup_group="grpA"`
posé sur t1001-100 ET t1001-101, appel de test qui fait sonner t1001-100
(`originate ... &park`), puis simulation d'un lookup dialplan `*8` avec
`variable_sip_from_user=t1001-101` (même groupe) -- l'action `intercept` générée
contient exactement l'UUID réel du canal en train de sonner, confirmé en comparant
avec `show channels as json` au même instant. Tout nettoyé après (pickup_group remis
à `NULL`, appel raccroché). Les 3 postes de test restent `Registered`.
Fichiers : sipv/backend/app/api/v1/endpoints/xml_curl.py.

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

### TASK-023.16 [x] Conversion automatique du format d'accueil vocal importé
Demande de l'utilisateur : importer un accueil dans N'IMPORTE QUEL format, converti
automatiquement vers le format attendu par le serveur (avant : upload brut, aucune
conversion, TASK-S008.2).

Fait : `ffmpeg` installé (apt, universe Ubuntu, même principe que kamailio/rtpengine
-- aucun dépôt tiers, absent avant cette tâche). `upload_greeting()` sauvegarde
d'abord le fichier brut, lance `ffmpeg -ar 8000 -ac 1 -acodec pcm_s16le` (WAV PCM
8kHz mono, même convention que les enregistrements d'appels TASK-023.4) via
`asyncio.create_subprocess_exec` (pas de `subprocess.run` bloquant dans une route
async), supprime le brut, renomme toujours en `.wav` (peu importe le format source).
Erreur de conversion (format non reconnu par ffmpeg) → 400 explicite plutôt qu'un
fichier corrompu silencieusement accepté.

Testé en direct avec un vrai fichier : ton de test généré en MP3 44.1kHz stéréo
(`ffmpeg -f lavfi sine=440`), uploadé sur une boîte vocale de test (poste 100) →
fichier résultant vérifié via `ffprobe` : `pcm_s16le, 8000 Hz, 1 channel` --
conversion confirmée réelle, pas juste renommée. Boîte vocale de test + fichier
supprimés après coup. Les 3 postes de test restent `Registered`.
Fichiers : sipv/backend/app/api/v1/endpoints/voicemail.py (ffmpeg installé
séparément sur le serveur, pas dans le dépôt git).

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

### TASK-023.12 [~] Sonnerie détaillée (interne/externe/file/silencieuse/règle caller ID)
Au-delà de `distinctive_ring` (S018.3, un seul champ). "Temps maximal de sonnerie" =
déjà `forward_no_answer_delay_seconds` (pas dupliqué) ; "volume imposé" = déjà
`forced_volume` (TASK-023.11, réglage partagé paging/sonnerie, pas dupliqué).

Migration `0035_ring_detail` : `ring_internal`, `ring_external`, `ring_queue`,
`silent_ring`, `caller_id_ring_rules` (format simple `"motif:sonnerie,motif2:..."`).

Câblé pour les appels INTERNES seulement (`_resolve_alert_info()`) : Alert-Info est
un header SIP standard -- FreeSWITCH le transmet, c'est le TÉLÉPHONE qui choisit
la sonnerie locale selon sa valeur (comme le Call-Info intercom de S023.11). Priorité :
silencieux > règle caller ID (motif trouvé dans le numéro de l'appelant) > sonnerie
interne spécifique > sonnerie distinctive générale (repli). Rien n'est ajouté si
aucun de ces champs n'est configuré (comportement identique à avant).

Testé en direct (bascule réelle sur t1001-101) : `silent_ring=true` -> header
`Alert-Info=<sip:silent>` confirmé dans le bridge généré ; `caller_id_ring_rules=
"100:vip-ring"` avec un appel simulé depuis t1001-100 -> `Alert-Info=<sip:vip-ring>`
correctement résolu (le motif "100" a matché le numéro de l'appelant). Remis à
`false`/`NULL` après vérification.

⚠️ [~] : `ring_external` (appel entrant DID, aucun trunk réel actif pour tester) et
`ring_queue` (mod_callcenter jamais alimenté, même limite que S007.2) restent
stockés mais PAS câblés -- pas de chemin d'appel réel à travers lequel les tester
honnêtement dans cet environnement pour l'instant.
Fichiers : sipv/backend/app/models/sip.py, api/v1/endpoints/xml_curl.py,
api/v1/endpoints/extensions.py, alembic/versions/0035_ring_detail.py.

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


### TASK-S041 [x] Fix — courriels cron root rebondissaient vers mail.simpleip.tel
Découvert en marge du module RDV ERPCRM (TASK-026, ERPCRM) : Philippe a reçu un
courriel avec l'expéditeur affiché "root" et aucun objet. Investigation via SSH
sur sipv-lab (192.168.1.55) :
- `/var/log/mail.log` montrait une tâche cron quotidienne de `root` (~519KB,
  probablement un rapport système type logwatch) à 06h25 chaque jour depuis au
  moins le 30 juillet, qui échouait avec "550 Sender verify failed" / "account
  may not exist" en tentant de relayer vers `mail.simpleip.tel`.
⚠️ Bug : `mydestination = localhost` seulement dans `/etc/postfix/main.cf`, sans
   `$myhostname` (sipv-lab) — Postfix ne reconnaissait donc pas `root@sipv-lab`
   comme une destination locale et tentait de le relayer via `relayhost`
   (mail.simpleip.tel) au lieu de le livrer localement dans /var/spool/mail/root.
   Ce relais échouait car mail.simpleip.tel n'autorise pas root@sipv-lab comme
   expéditeur valide, générant un rebond (bounce) qui lui-même repartait par le
   même chemin cassé.
   Fix : `postconf -e 'mydestination = $myhostname, localhost.localdomain, localhost'`
   + `postfix reload`. Vérifié par un envoi de test manuel (`sendmail root`) :
   `status=sent (delivered to mailbox)` au lieu de `bounced`. Boîte de test locale
   nettoyée après vérification.
Aucun fichier de code touché — configuration serveur uniquement
(`/etc/postfix/main.cf` sur sipv-lab).

### TASK-S042 [~] Fondation multi-serveur SIPV (pas le dispatcheur "classe 4" lui-même)
Contexte : Philippe a fourni un gros document d'architecture (rédigé avec
ChatGPT, qui ne connaît pas ~80% de ce qui a été construit ici) proposant entre
autres plusieurs serveurs SIPV (SIPV01/02/03) avec distribution des tenants et
un routeur DID central ("classe 4"/SBC). Analyse faite en direct avec Philippe
(comparaison document vs code réel, pas juste réaction au texte) : ⚠️ ça
contredisait a priori la décision de cette session de fixer `REG_DOMAIN="sipv"`
en dur (un seul domaine plat pour tous les tenants). Philippe a clarifié : il
n'a besoin que d'UN seul serveur aujourd'hui et probablement pour 5-6 ans, mais
il compte **vendre ce logiciel** — si un futur client a besoin de plusieurs
serveurs, l'architecture doit être prête. Décision prise ensemble : construire
la fondation de données MAINTENANT (coût quasi nul, un seul serveur = aucun
changement de comportement visible), mais **reporter le dispatcheur central
lui-même** (la vraie pièce technique qui redirigerait les appels/provisioning
vers le bon serveur) tant qu'un 2e serveur n'est pas réellement provisionné —
le construire aujourd'hui pour dispatcher entre... un seul serveur n'aurait
aucune valeur testable.

Fait :
- `backend/app/models/server.py` (nouveau) — `SipvServer` : name, hostname,
  ip_address, is_active, notes.
- `backend/app/models/tenant.py` — `Tenant.server_id` (FK nullable vers
  `sipv_servers`, `ondelete="SET NULL"`) + relation `server`.
- Migration `0044_sipv_servers.py` — crée `sipv_servers`, ajoute
  `tenants.server_id`, **seed automatique** d'un serveur "sipv-lab"
  (192.168.1.55) et **backfill** de tous les tenants existants dessus (aucun
  tenant ne se retrouve orphelin après la migration).
- `backend/app/api/v1/endpoints/servers.py` (nouveau) — CRUD minimal
  (`GET/POST /servers`, `PUT /servers/{id}`), compte de tenants par serveur.
- `backend/app/api/v1/endpoints/tenants.py` — `TenantOut` gagne
  `server_id`/`server_name` ; `create_tenant` assigne automatiquement le
  premier serveur actif trouvé (comportement "premier trouvé" temporaire — le
  futur dispatcheur central choisira intelligemment une fois plusieurs
  serveurs réels en place).
- `backend/app/main.py` — `include_router(servers.router, prefix="/api/v1/servers")`.

Déployé et testé en direct sur sipv-lab : migration appliquée
(`0043→0044` OK), service `sipv-backend` redémarré proprement (systemd),
vérifié directement en base : 1 serveur créé, tenant existant bien rattaché
(`server_id` non nul).

**Reste à faire (`[~]`)** :
- Le dispatcheur central lui-même ("classe 4"/SBC/DID Dispatcher — nom pas
  encore choisi, voir le document de Philippe pour les options de nommage) —
  reporté explicitement, à construire seulement quand un 2e serveur SIPV sera
  réellement provisionné.
- ~~Champ "serveur hébergeur" à afficher côté ERPCRM sur la fiche Compagnie~~ —
  **mise à jour (2026-08-02, TASK-023.27)** : `sipv_client.get_tenant`/
  `update_tenant` existent maintenant (ajoutés pour le catalogue d'options
  téléphonie, TASK-S011.5), donc le blocage technique noté ici n'existe plus.
  Il reste seulement à afficher `server_name` quelque part sur la fiche
  Compagnie ERPCRM (pas fait — personne ne l'a demandé encore).
- Onglet "Serveur" d'ERPCRM (créé vide cette session, TASK-026 côté nav) —
  cette fondation (liste des serveurs) en sera un des premiers contenus une
  fois qu'on y reviendra.

### TASK-S043 [ ] Architecture 3 couches (Serveur/Compagnie-Tenant/Contact-Poste) — backlog validé, rien construit
Philippe a retravaillé l'architecture globale avec ChatGPT (2026-08-02), sur la
base du premier document analysé pour TASK-S042 mais en beaucoup plus détaillé.
Objectif de cette entrée : ne pas perdre le résultat de cette réflexion et ne
pas la reconstruire ou la redemander plus tard. **Rien n'est construit ici** —
c'est un backlog de référence, validé contre le code réel, en attente de
priorisation.

**Déjà construit, confirmé aligné avec cette architecture (ne pas dupliquer)** :
- Héritage "As Template" (valeur absente = hérite du parent) : déjà le
  mécanisme de `resolve_setting()` (`app/core/settings_resolver.py`), utilisé
  pour plusieurs champs compagnie→poste (ex. `voicemail_delete_after_email`).
- Caller ID "As Company" avec override par poste : déjà `Tenant.
  default_caller_id_name/number` + `SIPExtension.caller_id_name/number`
  (nullable = hérite), plus `caller_id_internal_*`/`caller_id_external_*`
  (TASK-018.6).
- Objets partagés du tenant (IVR, groupes de sonnerie, files, horaires, jours
  fériés, paging) : déjà des modèles SIPV existants (`ivr.py`, `schedule.py`).
- E911 : `E911Address` (adresse civique par tenant) + `DID911Assignment`
  (DID→adresse) existent déjà — gestion manuelle, pas de déclencheur automatique.
- Catalogue d'options dynamique du poste (TASK-S011.5, commencé le même jour) :
  même principe que le "+ Ajouter une option" décrit ici, catalogue minimal
  pour l'instant (langue), extensible.
- Fondation multi-serveur (TASK-S042) : `SipvServer` + `Tenant.server_id`.

**Pas construit — nouveau, à prioriser plus tard (aucun GO donné)** :
1. **Global Templates / Model Templates / chaîne d'héritage à 5 niveaux**
   (défaut système/modèle → template global serveur → Global Policy tenant →
   template du tenant → template du modèle dans le tenant → poste individuel).
   Rien de tout ça n'existe. `PhoneButtonTemplate` (TASK-023.25) est le seul
   embryon de "template" actuel, et il ne couvre que les boutons, pas
   l'ensemble des paramètres d'un poste.
2. **Global Policy par tenant** — n'existe pas comme concept séparé, seulement
   les champs spécifiques déjà présents sur `Tenant` (permissions d'appel,
   caller ID par défaut).
3. **Registre 911 déclenché automatiquement** dès qu'un DID sert de Caller ID
   (compagnie, contact, groupe, file, site) + tableau de bord (nombre de DID
   affichés/complets/en erreur, taxe municipale 9-1-1 à remettre vs coût
   technique fournisseur — deux montants distincts, taux historisé par
   période). Rien de tout ça n'existe ; `E911Address`/`DID911Assignment`
   actuels sont gérés manuellement, sans déclencheur ni tableau de bord.
4. **Trunks / Routes entrantes / Routes sortantes en onglets de haut niveau**
   côté ERPCRM (pas nichés dans la fiche Compagnie). Le backend SIPV a déjà
   `trunks.py`/`routes.py` séparés, mais côté ERPCRM tout vit actuellement
   mélangé dans l'onglet Téléphonie de `CompanyDetail.jsx`. Irait
   naturellement dans l'onglet "Serveur" (créé vide, TASK-026).
5. **Catalogue de paramètres formalisé** (identifiant technique, type,
   validation, fabricants/modèles compatibles, dépendances) — on a
   actuellement juste une liste plate (`PHONE_OPTIONS_CATALOG`), pas cette
   structure riche.
   Démarré (2026-08-02, premier item du backlog attaqué) : voir TASK-023.28
   dans TASKERPCRM.md — uniquement côté ERPCRM (`ref_data.py`), rien touché
   côté SIPV pour cette étape.
6. Nettoyage explicitement demandé par Philippe : retirer toute notion propre
   à l'écosystème Grandstream (Wave, RemoteConnect, GDMS) de cette
   architecture — n'a jamais été construit ici de toute façon, juste à ne
   jamais l'introduire par erreur en copiant un concept UCM plus tard.

**Sources** : `/home/simpleip/GrandStream/schema_champs_ucm.md` (relevé complet
UCM6300A) et `/home/simpleip/Scopserv/SCHEMA~1.MD` (relevé complet ScopTel),
fournis par Philippe (2026-08-02) comme référence de structure de champs pour
construire ce catalogue plus tard — jamais de données client réelles dedans.
Dépend de : TASK-S042 (première ronde d'analyse architecture).

### TASK-S044 [x] Global/Tenant/Model Templates — chaîne d'héritage (item 1 de TASK-S043)
GO de Philippe (2026-08-02, "go") pour attaquer l'item 1 du backlog TASK-S043
juste après l'item 5 (TASK-S011.6/TASK-023.28, le catalogue formalisé sur
lequel cette chaîne s'appuie).

Relu `schema_champs_ucm.md` (lignes 1805-1827, onglet Zero Config de l'UCM
Grandstream) pour ancrer "Global Templates"/"Model Templates" sur leur vraie
définition plutôt que d'inventer : **Global Policy** = un seul gabarit
singleton appliqué à tous les appareils (déjà `Tenant.phone_option_defaults`,
TASK-S011.5). **Global Templates** = liste nommée de gabarits qui se
superposent à la Global Policy. **Model Templates** = liste nommée de
gabarits scopés à un modèle précis, avec un flag **Is Default** (celui
appliqué automatiquement en l'absence d'assignation explicite), superposés
au-dessus. Adapté au multi-tenant SIPV : Global Template devient scopé au
serveur (`SipvServer`, partagé par tous les tenants qu'il héberge) plutôt
qu'à l'appareil UCM unique ; le reste (Global Policy, Model Template)
devient scopé au tenant en plus du modèle.

Ordre de fusion retenu (le plus spécifique gagne, même esprit que
`resolve_setting()`/la fusion TASK-S011.5, juste étendue) :
défauts système (`PHONE_OPTION_SYSTEM_DEFAULTS`) → `GlobalTemplate`
(serveur, is_default) → `Tenant.phone_option_defaults` (Global Policy
tenant) → `TenantTemplate` (tenant, is_default) → `TenantModelTemplate`
(tenant+modèle, is_default) → `ProvisionedPhone.extra_config` (poste).

Fait (fondation seulement — modèles, migration, moteur de résolution) :
- 3 nouveaux modèles dans `models/provisioning.py` : `GlobalTemplate`
  (`server_id`), `TenantTemplate` (`tenant_id`), `TenantModelTemplate`
  (`tenant_id`+`phone_model_id`) — chacun `name`, `description`, `options`
  (JSON, mêmes clés que `PHONE_OPTIONS_CATALOG`), `is_default`, `is_active`.
- Migration `0046_template_inheritance_chain` (3 tables, appliquée sur le
  serveur réel, `alembic current` confirmé à jour).
- `get_phone_config` (`provisioning.py`) étendu pour interroger les 3
  nouvelles tables (filtre `is_default=true, is_active=true`) et les
  fusionner dans l'ordre ci-dessus.
- Testé de bout en bout sur le GXP2135 physique réel (t1001-102,
  `25ed81cf-d6a7-4209-a1a1-39ea108c9a6c`) : baseline `P1362=fr` (Tenant.
  phone_option_defaults), `TenantTemplate` (language=auto) posé → rendu
  passe à `auto` (gagne sur la Global Policy tenant), `TenantModelTemplate`
  (language=fr) posé par-dessus → rendu repasse à `fr` (gagne sur
  `TenantTemplate`, confirme l'ordre du plus spécifique) — les 3 lignes de
  test supprimées après coup, aucune donnée réelle laissée modifiée, poste
  `t1001-102` reconfirmé `Registered` après redémarrage des 2 services
  (`sipv-backend`, `sipv-backend-tls`).

**CRUD + UI ajoutés le même jour (2026-08-02→03)**, GO de Philippe ("on construit
cette écran... on choisira le gxp2135") :
- CRUD complet (list/create/update/delete) pour les 3 niveaux :
  `provisioning.py` (`/tenant-templates`, `/tenant-model-templates`, tenant_id
  dans le body/path) et `servers.py` (`/{server_id}/global-templates`,
  `/global-templates/{id}`) côté SIPV, tous en `get_current_user_or_service`
  pour le proxy ERPCRM. `list_servers` (servers.py) passé du même
  `get_current_user` au `get_current_user_or_service` (ERPCRM ne pouvait pas
  l'appeler avant).
- Poser `is_default=true` désactive automatiquement le `is_default` existant
  au même scope (`update(...).where(scope==X).values(is_default=False)` avant
  l'insert/update) -- couvre le manque `is_default` note plus haut (devient un
  besoin reel une fois l'UI interactive construite, plus seulement theorique).
- ERPCRM : `sipv_client.py` (12 nouvelles fonctions), proxy `companies.py`
  (`/tenant-templates`, `/tenant-model-templates`, scope compagnie -- meme
  pattern que `button-templates`), nouveau fichier `server.py` (proxy
  `/servers`, `/servers/{id}/global-templates` -- rien n'existait encore pour
  la page Serveur), enregistré dans `main.py`.
- Frontend : `CompanyDetail.jsx` (onglet Téléphonie) → `TenantTemplatesSection`
  et `TenantModelTemplatesSection` (sélecteur marque/modèle réutilisant le même
  `Autocomplete` deux-étapes que `ContactDetail.jsx`, 70 modèles Grandstream
  déjà au catalogue -- confirmé, aucun autre fabricant encore). `Server.jsx`
  (page vide TASK-026) → liste des serveurs + `GlobalTemplatesSection` par
  serveur. Chaque template expansible affiche un `PhoneOptionsEditor` (déjà
  existant, réutilisé tel quel) pour éditer ses `options`.
- Testé de bout en bout via l'API ERPCRM réelle (pas juste SIPV direct cette
  fois) : token JWT généré pour l'utilisateur admin réel, `GET
  /v1/ref/phone-models` confirme GXP2135 présent, `POST .../tenant-model-
  templates` créé pour la compagnie Simple IP inc. (GXP2135, is_default=true,
  language=auto) → rendu du poste physique t1001-102 passé de `fr` à `auto` →
  supprimé via `DELETE` proxy → rendu revenu à `fr`, poste confirmé
  `Registered` après coup. `npx vite build` (ERPCRM frontend) propre, aucune
  erreur de compilation.
- Backend ERPCRM (processus `uvicorn` manuel, pas de service systemd actif
  actuellement -- `erpcrm-backend`/`erpcrm-backend-tls` systemd restent
  `inactive`) tué proprement (PID confirmé disparu) et relancé -- healthcheck
  `/api/health` OK après coup.

Explicitement toujours pas fait (pas de besoin réel, LOI 4) :
- Aucune assignation explicite d'un template non-`is_default` à un tenant/
  poste précis (seul le défaut par niveau est automatique). Le même
  mécanisme "créer puis appliquer" que `PhoneButtonTemplate` (TASK-023.25)
  pourrait s'y greffer plus tard si demandé.
- Génération automatique de `config_template` pour un nouveau modèle/marque —
  chaque modèle a toujours besoin de son propre gabarit Jinja2 écrit à la main
  (traduction option→code fabricant, ex. `P1362` chez Grandstream) ; la chaîne
  d'héritage est générique pour tout `PhoneModel` existant, mais rien
  n'automatise l'ÉCRITURE de ce gabarit pour un modèle qui n'en a pas encore.
Fichiers : backend/app/models/provisioning.py, models/__init__.py,
api/v1/endpoints/provisioning.py, api/v1/endpoints/servers.py,
alembic/versions/0046_template_inheritance_chain.py (SIPV) ;
backend/app/core/sipv_client.py, api/v1/endpoints/companies.py,
api/v1/endpoints/server.py (nouveau), main.py, frontend/src/pages/
CompanyDetail.jsx, frontend/src/pages/Server.jsx (ERPCRM).
Dépend de : TASK-S043 (item 1), TASK-S011.6/TASK-023.28 (item 5, catalogue).

### TASK-S044.1 [x] Choix explicite des templates + bibliothèque par serveur (correction de placement)
Corrigé le même jour (2026-08-03) suite au test de l'écran TASK-S044/TASK-027.1
par Philippe : "Template de tenant" avait été créé DANS Compagnie (donnée
privée par tenant), pas correct selon son modèle mental de la hiérarchie
Serveur → Compagnie → Contact ("create template" doit être dans la couche
supérieure, le CHOIX dans la couche adéquate). Il a aussi demandé un mécanisme
"as template" par champ (valeur du template affichée avec étiquette
"(as template)", personnalisable champ par champ, réversible).

Changements structurels :
- `TenantTemplate.tenant_id` → `server_id` : devient une bibliothèque PAR
  SERVEUR (comme `GlobalTemplate`), créée/gérée dans Serveur uniquement.
  Migration `0047_template_explicit_selection` (table vidée avant l'ALTER --
  seulement 1 ligne de test de Philippe dedans, aucune donnée réelle).
- Résolution de la chaîne changée de "scan is_default" à référence explicite :
  `Tenant.selected_tenant_template_id` (nouveau, nullable) et
  `ProvisionedPhone.selected_tenant_model_template_id` (nouveau, nullable).
  Si non choisi, le niveau est simplement sauté (pas de devinette). Seul
  `GlobalTemplate` (niveau serveur) reste automatique via `is_default` --
  c'est une "policy", pas un choix par compagnie.
- `TenantModelTemplate` INCHANGÉ (reste créé dans Compagnie, confirmé correct
  par Philippe) -- seul le mécanisme de sélection devient explicite
  (`selected_tenant_model_template_id`, choisi dans Contact).
- CRUD `TenantTemplate` déplacé de `provisioning.py` vers `servers.py`
  (`GET/POST/PUT/DELETE /servers/{server_id}/tenant-templates`, mémé forme
  que `global-templates`).
- `PhoneOptionsEditor.jsx` (composant partagé ERPCRM) réécrit pour le
  mécanisme "as template" : accepte `templateOptions`/`templateLabel`, affiche
  automatiquement toute option couverte par le template actif avec l'étiquette
  "(as template)" (cliquable pour revenir au template une fois personnalisée),
  en plus des options ajoutées manuellement (`+ Ajouter une option`, inchangé).
- ERPCRM `Server.jsx` : ajout de `TenantTemplatesSection` (bibliothèque, pas de
  "Défaut" affiché puisque jamais automatique). `CompanyDetail.jsx` : retiré le
  CRUD local, ajouté un sélecteur au-dessus de "Options téléphonie (défaut
  compagnie)". `ContactDetail.jsx` : bloc "Options du poste" + sélecteur de
  template par modèle déplacé de la section appareil vers entre Renvois et
  Caller ID (demande explicite de placement). Nouveau endpoint `GET
  /contacts/{id}/sip-extension/phone/tenant-model-templates` (filtre déjà au
  modèle du poste, évite d'exposer `companyId` côté Contact).

Testé de bout en bout via l'API ERPCRM réelle (token admin, pas juste SIPV
direct) sur le GXP2135 physique (t1001-102) : template tenant créé dans
Serveur → sélectionné dans Compagnie → rendu changé (fr→auto) ; template par
modèle créé dans Compagnie → sélectionné dans Contact → rendu regagne (auto→fr,
plus spécifique) ; tout désélectionné/supprimé après coup → rendu revenu à fr
(baseline), poste confirmé `Registered`. Tables `tenant_templates`/
`tenant_model_templates`/`global_templates` vides après nettoyage (confirmé
par requête directe).

Explicitement pas fait : assignation de template non liée à "choisi" (pas de
liste de templates "disponibles mais non actifs" appliqués partiellement) ;
mécanisme "as template" pas étendu aux champs Caller ID/Renvois existants
(nullable columns, mécanisme différent et déjà fonctionnel -- Philippe a
seulement demandé le PLACEMENT du nouveau bloc à côté, pas la fusion des deux
mécanismes).
Fichiers : backend/app/models/provisioning.py, models/tenant.py,
api/v1/endpoints/provisioning.py, api/v1/endpoints/servers.py,
api/v1/endpoints/tenants.py, alembic/versions/0047_template_explicit_selection.py
(SIPV) ; backend/app/core/sipv_client.py, api/v1/endpoints/companies.py,
api/v1/endpoints/server.py, api/v1/endpoints/contacts.py,
frontend/src/components/PhoneOptionsEditor.jsx, frontend/src/pages/
CompanyDetail.jsx, frontend/src/pages/Server.jsx, frontend/src/pages/
ContactDetail.jsx (ERPCRM).
Dépend de : TASK-S044.

### TASK-S011.7 [x] Catalogue PhoneModel — 20 marques additionnelles (liste seulement)
Demande de Philippe (2026-08-03) : liste complète marque/modèle fournie
(259 entrées, 21 marques dont Alcatel, AudioCodes, Cisco, CyberData,
CounterPath, Fanvil, FlyingVoice, Grandstream, Hitachi, LG-Ericsson,
Mitel/Aastra, Panasonic, Polycom, Linksys/Sipura, Snom, Tiptel, Uniden, Voice
Operator Panel, VTech, Yealink, Other) — explicitement "on ne fait pas les
code juste la liste" : entrées catalogue seulement, AUCUN `config_template`
écrit (reste un chantier séparé par modèle, comme déjà pour le GXP2135).

Migration `0048_seed_more_brands` : idempotente (n'insère que les paires
brand+model absentes, exact match), guard par (brand, model) plutôt que par
brand seul (les modèles Grandstream de sa liste chevauchaient partiellement
le catalogue déjà seedé, TASK-023.18/0039 — doublons exacts ignorés, 26
nouveaux modèles Grandstream réellement ajoutés). `device_type` classé
UNIQUEMENT par mot-clé explicite dans le nom fourni (Intercom/Softphone/
Gateway → intercom/softphone/ata), `telephone` par défaut pour tout le reste
y compris les combinés sans-fil DECT/Wireless — pas de classification basée
sur une connaissance produit externe non vérifiée (zéro supposition).

Vérifié après coup : 21 marques / 319 modèles au total dans `phone_models`,
comptes par marque recomptés et confirmés identiques à ceux donnés par
Philippe (ex. Cisco 31, Yealink 41, Grandstream 96 = 70 déjà là + 26
nouveaux). Aucun doublon GXP2135. Confirmé visible via `/v1/ref/phone-models`
(endpoint déjà utilisé par les sélecteurs marque/modèle côté ERPCRM). Poste
t1001-102 reconfirmé `Registered` après la migration.
Fichiers : backend/alembic/versions/0048_seed_more_brands.py.
Dépend de : TASK-023.18 (catalogue Grandstream initial).

### TASK-S011.8 [x] Pack vocal français FreeSWITCH + lien avec la langue du poste
Demande de Philippe (2026-08-03) : installer le pack de voix française pour
FreeSWITCH (annonces boîte vocale/IVR — distinct de P1362, la langue
d'affichage du téléphone) et lier les deux pour qu'ils suivent le même choix.

Vérifié avant d'agir (zéro supposition) : sur le serveur réel, seul le pack
anglais (`en/us/callie`) était installé. Pack officiel FreeSWITCH pour le
français canadien identifié via le Makefile source
(`/usr/src/freeswitch-1.10.12`) : `sounds-fr-ca-june` (voix "June", 8kHz,
version 1.0.51) — pas `fr-fr`, le seul pack français officiel disponible est
canadien, cohérent avec la clientèle Simple IP.

Fait :
- `sudo make sounds-fr-install` exécuté sur le serveur réel (télécharge depuis
  `files.freeswitch.org`, installe sous `/usr/local/freeswitch/sounds/fr/ca/june/`)
  — confirmé présent après coup.
- `xml_curl.py` (`_user_xml`) : nouvelle table `_LANGUAGE_PROMPT_MAP` (`fr` →
  fr/ca/june, `en` → en/us/callie), pose `default_language`/`default_dialect`/
  `default_voice`/`sound_prefix` par poste selon `Tenant.phone_option_defaults
  ["language"]` (même clé que le catalogue TASK-S011.5/S011.6/P1362). "auto"
  ou absent → aucune variable posée, le défaut global (`en/us/callie`,
  `vars.xml`) s'applique tel quel.
- Portée volontairement limitée au niveau **Tenant** (déjà chargé dans
  `_handle_directory`, zéro requête supplémentaire) — PAS la chaîne complète à
  5 niveaux (TASK-S044) : ce endpoint est appelé à CHAQUE REGISTER/INVITE
  authentifié (chemin sensible à la performance), et personne n'a encore
  demandé de précision par poste pour les annonces vocales (contrairement au
  texte affiché à l'écran, où TASK-S044 reste la source de vérité).

Testé en direct sur le tenant réel (t1001) : `default_language=fr` confirmé
dans la réponse XML directory pour t1001-102 avec `phone_option_defaults=
{"language":"fr"}` ; basculé à `"auto"` → aucune variable posée (confirmé) ;
remis à `"fr"` (baseline restaurée). Poste `t1001-102` resté `Registered`
tout au long du test.

Catalogue ERPCRM (`ref_data.py`) : choix `en` (Anglais) ajouté à l'option
`language` — confiance moindre que `fr`/`auto` (déduit par analogie avec le
changelog Grandstream GXW42xx, aucune légende P1362 officielle trouvée pour
la famille GXP2130/40/60/70/35 elle-même — voir TASK-023.28 pour le détail).

Explicitement pas fait : résolution complète à 5 niveaux pour les annonces
vocales (voir portée ci-dessus) ; autres langues (zh/es existent dans
l'écosystème P-code Grandstream mais aucun pack vocal FreeSWITCH correspondant
installé, aucun besoin réel exprimé).
Fichiers : backend/app/api/v1/endpoints/xml_curl.py (SIPV, code) ; pack sons
installé hors dépôt git (fichiers binaires sur le serveur uniquement).
Dépend de : TASK-S011.5/S011.6 (catalogue "language").

### TASK-S010.3 [x] UI Succursales (911 multi-site) — ERPCRM
Demande de Philippe (2026-08-03) : "succursale" pour avoir plusieurs sites
dans le même tenant, permettant plusieurs adresses 911. Vérifié avant de
construire quoi que ce soit : la fondation existait déjà en ENTIER côté SIPV
depuis TASK-S010/TASK-S010.2 — `E911Address` n'a jamais été limité à une
seule adresse par tenant (déjà un `label` par adresse, ex. "Bureau
principal"), et `ExtensionE911Assignment` lie déjà chaque poste à UNE adresse
au choix. Il ne manquait AUCUNE pièce de données, seulement l'UI côté ERPCRM
(confirmé par grep : zéro référence à `E911Address`/`e911` dans le frontend
ERPCRM avant cette tâche).

Fait :
- `e911.py` (SIPV) : les 15 endpoints passés de `get_current_user` à
  `get_current_user_or_service` (même conversion que `tenants.py`/
  `servers.py` plus tôt) pour permettre le proxy ERPCRM.
- `sipv_client.py` : 8 nouvelles fonctions (adresses + assignation par poste).
- `companies.py` : proxy `/{company_id}/e911-addresses[...]` (CRUD complet,
  "Succursales").
- `contacts.py` : `GET /{contact_id}/sip-extension/911/addresses` (liste
  filtrée au tenant du poste, pas besoin de `companyId` côté Contact — même
  pattern que TASK-S044.1) ; `GET/PUT/DELETE /{contact_id}/sip-extension/911`
  (upsert — le frontend n'a pas à savoir si une assignation existe déjà).
- `CompanyDetail.jsx` (Téléphonie) : `E911AddressesSection` — liste/créer/
  modifier/supprimer des succursales (nom + adresse civique complète).
- `ContactDetail.jsx` : section "911 — localisation d'urgence" (entre Caller
  ID et Plan d'appel) — sélection de succursale + étage/bureau/précision/
  courriel d'alerte.

Testé de bout en bout via l'API ERPCRM réelle (token admin) sur la vraie
compagnie/le vrai poste : succursale créée, listée via l'endpoint Contact,
assignée au poste, mise à jour (même ligne réutilisée, pas de doublon —
confirmé par requête directe SIPV), assignation et succursale supprimées,
tables `e911_addresses`/`extension_911_assignments` vides après coup. Poste
t1001-102 resté `Registered`. `npx vite build` propre.

Explicitement pas fait (aucun besoin exprimé) : validation d'adresse auprès
d'un fournisseur (`is_validated`/`carrier_reference` existent déjà comme
champs, pas de flux d'automatisation) ; lien DID↔911 (existe déjà séparément,
`DID911Assignment`, non touché ici, portait déjà sur les DID pas les postes).
Fichiers : backend/app/api/v1/endpoints/e911.py (SIPV) ;
backend/app/core/sipv_client.py, api/v1/endpoints/companies.py,
api/v1/endpoints/contacts.py, frontend/src/pages/CompanyDetail.jsx,
frontend/src/pages/ContactDetail.jsx (ERPCRM).
Dépend de : TASK-S010, TASK-S010.2.

### TASK-S044.2 [x] Templates choisissables PLUSIEURS a la fois + visibilite du Global dans Compagnie
Demande de Philippe (2026-08-03), en testant TASK-S044.1 : il avait créé
"Global Français" (Défaut) et "Global Anglais" (orphelin, aucun mécanisme de
choix à ce niveau) — a demandé de pouvoir CHOISIR un ou PLUSIEURS Global
Templates en plus de celui automatique, que ce choix soit visible dans les
"Options téléphonie" de la Compagnie, et le même principe partout : "celui
par défaut ET un autre qui ajoute l'oreillette ET un autre qui ajoute des
boutons de park" — des templates qui SE COMBINENT, pas juste un choix parmi
plusieurs.

Migration `0049_template_multi_select` : les 3 FK simples (un seul choix)
converties en tableaux UUID (plusieurs choix, fusionnés dans l'ordre du
tableau — le dernier gagne en cas de clé en commun) :
- `Tenant.selected_tenant_template_id` → `selected_tenant_template_ids`
- `Tenant.selected_global_template_ids` (NOUVEAU — Global Templates
  supplémentaires choisis par la compagnie, en PLUS de celui `is_default`
  qui reste automatique/"policy")
- `ProvisionedPhone.selected_tenant_model_template_id` → `..._ids`
Pas de contrainte FK Postgres sur les éléments de tableau (même esprit que
`blocked_countries`/`blocked_prefixes` déjà dans le projet) — intégrité gérée
côté application.

Ordre de fusion (`get_phone_config`) : système → GlobalTemplate is_default
(auto) → GlobalTemplate(s) supplémentaires choisis (dans l'ordre du tableau)
→ Global Policy tenant (`phone_option_defaults`) → TenantTemplate(s) choisis
→ TenantModelTemplate(s) choisis → poste. Chaque niveau peut maintenant
empiler plusieurs templates.

Frontend : les 3 `<select>` à choix unique remplacés par des listes de cases
à cocher (Serveur reste inchangé — c'est là qu'on les crée). `CompanyDetail.jsx`
calcule maintenant `effectiveTemplateOptions` (fusion de TOUT ce qui est
au-dessus de `phone_option_defaults` : Global auto + Global choisis + Tenant
choisis) et le passe à `PhoneOptionsEditor` — le Global automatique est donc
maintenant VISIBLE ("as template") même sans aucune sélection, répond
directement à "si il est par défaut l'afficher dans le template de
compagnie". Nouveau `GET /companies/{id}/global-templates` (miroir de
`tenant-templates`) pour lister les Global disponibles côté Compagnie.

Testé de bout en bout sur le vrai GXP2135 avec les VRAIS templates de
Philippe : "Global Anglais" (non-défaut) sélectionné en supplément → n'a PAS
changé le rendu tant que `phone_option_defaults` (plus spécifique) contenait
déjà `fr` (comportement CORRECT, pas un bug — confirmé en vidant
temporairement `phone_option_defaults` : "Global Anglais" a alors bien gagné
sur "Global Français" par défaut). Même vérification au niveau poste avec un
template de test (créé/assigné/confirmé/supprimé). Tout remis à l'état
d'origine après coup — les 2 vrais templates de Philippe (Global Français/
Anglais, Français/Anglais tenant) laissés intacts, aucune donnée de test
résiduelle. Poste t1001-102 resté `Registered` tout du long.

Explicitement pas fait : "oreillette"/"boutons de park" ne sont PAS des
options réelles du catalogue (`PHONE_OPTIONS_CATALOG` n'a toujours qu'une
seule option, `language`) — rien inventé pour faire une démo, ces exemples
de Philippe décrivent l'usage prévu une fois le catalogue enrichi (chantier
séparé, ajouter ces options quand le besoin réel se présente).
Fichiers : backend/app/models/tenant.py, models/provisioning.py,
api/v1/endpoints/tenants.py, api/v1/endpoints/provisioning.py,
alembic/versions/0049_template_multi_select.py (SIPV) ;
backend/app/api/v1/endpoints/companies.py, api/v1/endpoints/contacts.py,
frontend/src/pages/CompanyDetail.jsx, frontend/src/pages/ContactDetail.jsx
(ERPCRM).
Dépend de : TASK-S044.1.

### TASK-S023.29 [x] UI Boîte vocale (checkbox activer + options) — gap complet trouvé
Demande de Philippe (2026-08-03) : en appelant le poste 100, "messagerie
vocale activée" affiché mais impossible à désactiver ; voulait une checkbox
qui, une fois cochée, révèle les options de boîte vocale (mot de passe, etc.).

Vérifié avant de coder (zéro supposition) : gap total confirmé côté ERPCRM
(zéro référence à `VoicemailBox` dans tout le frontend) — la ligne
"Activée/Désactivée" était un texte en LECTURE SEULE, jamais éditable.
Encore plus révélateur : le poste 100 avait `voicemail_enabled=true` en DB
mais AUCUNE ligne `VoicemailBox` (seuls 101/102 en avaient, créées
manuellement pendant des tests antérieurs, jamais via une UI) — le drapeau
disait "activée" mais rien de fonctionnel n'existait derrière.

Fait :
- `voicemail.py` : 5 endpoints (list/create/update/delete + le get_global déjà
  là) passés à `get_current_user_or_service`. ⚠️ Bug trouvé en testant le
  DELETE via clé de service : `user.email` encore utilisé sans garde dans
  `delete_voicemail` (les autres l'avaient déjà) → `AttributeError` (500)
  quand appelé sans JWT utilisateur. Corrigé (`user.email if user else
  "erpcrm-service"`), même pattern que les autres endpoints.
- `sipv_client.py` (ERPCRM) : 4 fonctions (list/create/update/delete).
- `contacts.py` (ERPCRM) : `SipExtensionUpdate.voicemail_enabled` ajouté (la
  checkbox elle-même) ; `GET/PUT/DELETE /{contact_id}/sip-extension/voicemail`
  (upsert -- le frontend n'a pas à savoir si la boîte existe déjà ; DELETE =
  `is_active=false`, PAS une suppression réelle -- réversible).
- `ContactDetail.jsx` : checkbox "Boîte vocale activée" (remplace le texte en
  lecture seule) ; cochée → révèle courriel, NIP, 3 cases à cocher (courriel
  par nouveau message, joindre le fichier audio, sauter les instructions
  parlées). Cocher pour la première fois crée la boîte tout de suite
  (mailbox = numéro de poste, nom = nom du contact). Section positionnée
  juste avant DND (placement demandé explicitement).

**Révisé le même jour** (retour de Philippe après avoir vu l'écran) :
- NIP boîte vocale rendu directement visible/éditable (retiré le pattern
  "vide = inchangé" copié par réflexe d'ailleurs dans le projet où il est
  justifié -- mots de passe SIP chiffrés, mot de passe admin téléphone). Ici
  non justifié : `VoicemailBox.password` est DÉJÀ stocké en clair (jamais
  chiffré nulle part dans `voicemail.py`) -- c'est un NIP composé au clavier
  du téléphone (convention Asterisk/FreeSWITCH mod_voicemail), pas un mot de
  passe de connexion. `VoicemailOut.password` ajouté (jamais fait pour les
  autres secrets du projet -- délibérément différent ici, la donnée
  sous-jacente n'a jamais été un secret protégé).
- Section déplacée : elle vivait après Renvois/Caller ID/911 (placement par
  défaut, pas demandé) ; déplacée juste avant DND (haut de la fiche,
  placement explicitement demandé cette fois).

Testé de bout en bout via l'API réelle sur le VRAI poste 100 : désactivé,
réactivé, boîte créée (mailbox="100", fullname="Test Un" auto-déduit),
courriel + mot de passe modifiés (mot de passe confirmé changé en DB),
désactivée (confirmé `is_active=false`, pas supprimée), puis supprimée pour
de vrai (donnée de test) et `voicemail_enabled` remis à son état d'origine
(`true`). Poste physique t1001-102 resté `Registered` tout du long.
`npx vite build` propre.

Explicitement pas fait (aucun besoin exprimé) : gestion des messages/
transcription/salutations (greetings) — endpoints déjà tout faits côté SIPV
mais aucune UI, `max_messages`/`max_message_length`/`language` (avancé, pas
demandé).
Fichiers : backend/app/api/v1/endpoints/voicemail.py (SIPV) ;
backend/app/core/sipv_client.py, api/v1/endpoints/contacts.py,
frontend/src/pages/ContactDetail.jsx (ERPCRM).

### TASK-S023.31 [~] Bug critique BV corrigé (domain_name jamais posé) + accueil upload/download
Philippe a appelé le vrai poste 100 (2026-08-04) : ça sonne, tombe sur la BV,
dit "the person at extension... goodbye!" et raccroche -- **pas de bip, pas
moyen de laisser un message**. Aussi signalé : poste jamais annoncé par son
nom, et voulait un endroit pour télécharger/uploader le message d'accueil.

**Cause racine trouvée dans les vrais logs FreeSWITCH** (zéro supposition) :
`voicemail(default  t1001-100)` -- double espace = `${domain_name}` VIDE au
moment d'appeler l'app `voicemail`. Confirmé par la suite du log : joue
seulement `vm-person.wav` puis `vm-goodbye.wav` et raccroche -- exactement le
comportement d'échec de `mod_voicemail` quand il ne peut pas localiser le
compte (pas de nom personnalisé, pas de bip, pas d'enregistrement possible).

`domain_name` n'était posé NULLE PART avant les 6 appels à l'app `voicemail`
dans `xml_curl.py`, sauf un endroit (routage DID entrant) qui le posait à la
mauvaise valeur (`REG_DOMAIN` = constante générique `"sipv"`, pas le domaine
réel du tenant). Corrigé aux 5 endroits qui touchent le flux normal d'un
poste (*97, *98+poste, DND, **le chemin exact qu'il a testé** -- sonne, pas
de réponse, tombe sur BV -- et routage DID entrant) : `<action
application="set" data="domain_name={tenant.account_number}"/>` posé juste
avant chaque appel à `voicemail`. PAS corrigé : les options "voicemail" dans
un menu IVR (`_ivr_option_action`) -- même bug latent probable, mais hors du
chemin qu'il testait, pas touché pour rester ciblé sur le problème signalé.

Vérifié après coup (dialplan régénéré pour le poste 100 réel) : le XML
contient maintenant bien `<action application="set" data="domain_name=t1001"/>`
juste avant `voicemail(default ${{domain_name}} t1001-100)`. **Limite
honnête** : je ne peux pas placer un vrai appel depuis cet environnement --
la correction est vérifiée structurellement (le bon XML est généré, cause
racine confirmée par les logs), mais PAS reconfirmée par un vrai appel qui
laisse effectivement un message. Philippe doit retester en direct.

Accueil (greeting) upload/download/suppression -- l'infrastructure
(conversion ffmpeg vers WAV 8kHz mono, déjà en place côté SIPV) existait mais
aucune UI : `voicemail.py` (3 endpoints passés à `get_current_user_or_
service`) ; `sipv_client.py` (3 fonctions, dont le transfert multipart) ;
`contacts.py` (`POST/GET/DELETE /{{contact_id}}/sip-extension/voicemail/
greeting`, scope au type "unavailable" -- celui joué quand personne ne
répond, le cas exact signalé ; les types busy/name/temp existent côté SIPV
mais pas exposés ici, pas demandés) ; `ContactDetail.jsx` (section dans
"Boîte vocale" : indicateur présent/absent, télécharger, envoyer un fichier
audio -- n'importe quel format, conversion automatique).

Testé de bout en bout via l'API réelle sur la vraie boîte du poste 100 :
fichier WAV de test envoyé (converti correctement, 8kHz mono confirmé),
téléchargé (contenu WAV valide confirmé), supprimé (fichier disparu du
disque confirmé). Poste t1001-102 resté `Registered` tout du long.

[~] volontairement : la cause du bug "pas de bip/pas de message" est
identifiée et corrigée avec de bonnes preuves (logs réels + XML régénéré
correct), mais reste à confirmer par un vrai appel de Philippe avant de
marquer [x].
Fichiers : backend/app/api/v1/endpoints/xml_curl.py, voicemail.py (SIPV) ;
backend/app/core/sipv_client.py, api/v1/endpoints/contacts.py,
frontend/src/pages/ContactDetail.jsx (ERPCRM).

### TASK-S023.32 [x] Suite TASK-S023.31 : annonce dit "100" pas "t1001-100" + sonneries + auto-save
Philippe a retesté et signalé 3 choses (2026-08-04) :

1. **L'annonce générique disait le username SIP complet** ("t1001-100") au
   lieu du numéro de poste ("100"). Cause : les actions `voicemail()`
   passaient `ext.username` comme mailbox, pas `ext.extension`. Corrigé aux 4
   endroits concernés (`_forward_action_xml`, DND, timeout de sonnerie,
   routage DID entrant). ⚠️ Ce changement cassait la recherche interne de
   `mod_voicemail` (action=voicemail-lookup, qui envoie maintenant "100" au
   lieu de "t1001-100") -- ajouté un repli dans `_handle_directory` : si le
   lookup par username échoue ET que c'est cette action précise ET qu'un
   tenant est déjà résolu par le domaine, réessaye par numéro d'extension nu
   scopé à ce tenant. Jamais actif pour un vrai REGISTER (qui envoie toujours
   le username complet, matche déjà avant ce repli). Testé en direct : lookup
   `user=100&domain=t1001&action=voicemail-lookup` retrouve bien le bon
   compte ; lookup normal `user=t1001-102` inchangé ; poste `Registered`.

2. **Bouton "Enregistrer" de la BV semblait ne rien faire.** Vérifié dans les
   logs ERPCRM + la DB : les PUT partaient bien et étaient bien sauvegardés
   (courriel de Philippe confirmé en base) -- le vrai problème était l'absence
   totale de retour visuel. Remplacé par sauvegarde automatique par champ
   (courriel/NIP au `onBlur`, cases à cocher au `onChange`) avec le même
   indice bleu que `PhoneOptionsEditor` (TASK demande du 2026-08-04) -- plus
   de bouton groupé, plus de confusion possible.

3. **"Nombre de sonneries avant messagerie" introuvable dans la section
   Boîte vocale.** Le champ existe déjà (`forward_no_answer_delay_seconds`,
   SIPExtension) mais son UI n'apparaissait que si un renvoi explicite était
   configuré (`forward_no_answer_enabled`) -- jamais pour le cas simple
   (`voicemail_enabled` seul) qui est pourtant le seul câblé chez lui. Ajouté
   directement dans la section Boîte vocale, exprimé en NOMBRE DE SONNERIES
   (pas en secondes) -- conversion basée sur la cadence réelle configurée sur
   ce serveur (`vars.xml`, `us-ring=%(2000,4000,...)` = 2s son + 4s silence =
   6s/sonnerie, vérifié, pas inventé). 20s par défaut = ~3 sonneries, cohérent
   avec son observation initiale ("ça sonne 4 coups").

Fichiers : backend/app/api/v1/endpoints/xml_curl.py (SIPV) ;
frontend/src/pages/ContactDetail.jsx (ERPCRM).
Dépend de : TASK-S023.31.

### TASK-S023.33 [x] Layout Boîte vocale + indice bleu invisible + NIP par défaut configurable
Suite de retours de Philippe (2026-08-04) sur l'écran juste construit :

1. **Champs "Sonneries"/"NIP" gigantesques** — ils partageaient `.ifields-grid`
   (2 colonnes égales) avec Courriel, qui a besoin d'être large. Remplacé par
   une rangée flex avec largeurs explicites (Sonneries 64px, NIP 120px,
   Courriel prend le reste).
2. **Indice bleu de sauvegarde invisible** — cause réelle : réseau local
   souvent <50ms, le bleu apparaissait et disparaissait plus vite qu'un
   rafraîchissement d'écran perceptible. Durée minimum garantie (400ms)
   ajoutée à `PhoneOptionsEditor.jsx` ET au formulaire BV (même bug latent
   aux deux endroits, corrigé aux deux).
3. **NIP jusqu'à 8 caractères** (la plupart en auront 4) — `maxLength=20`
   ajouté (limite réelle de la colonne DB, pas arbitraire), largeur du champ
   élargie en conséquence.
4. **NIP par défaut des nouvelles BV, configurable** — nouveau champ
   `TelephonySettings.voicemail_default_password` (migration
   `0050_vm_default_password`, nullable = comportement précédent inchangé,
   NIP aléatoire 4 chiffres). `create_voicemail` : NIP fourni explicitement >
   NIP par défaut configuré > aléatoire (dernier recours). Section "Boîte
   vocale — réglages globaux" ajoutée dans **Serveur** (ERPCRM) — c'est un
   singleton `TelephonySettings`, pas un réglage par `SipvServer`, donc rendu
   une seule fois en haut de la page, pas par serveur. `get_current_user` →
   `get_current_user_or_service` sur `/global-settings` (SIPV) pour permettre
   le proxy.

Testé : réglage global lu (`null` au départ) → réglé à "8123" (valeur donnée
par Philippe) → relu, confirmé persisté. Poste t1001-102 resté `Registered`.
`npx vite build` propre.
Fichiers : backend/app/models/settings.py, api/v1/endpoints/voicemail.py,
alembic/versions/0050_vm_default_password.py (SIPV) ;
backend/app/core/sipv_client.py, api/v1/endpoints/server.py,
frontend/src/components/PhoneOptionsEditor.jsx,
frontend/src/pages/ContactDetail.jsx, frontend/src/pages/Server.jsx (ERPCRM).
Dépend de : TASK-S023.32.

### TASK-S040.1 [ ] Softphone SimpleIP pour ordinateur (compagnon du mobile TASK-S040)
Demande de Philippe (2026-08-02), en même temps que la discussion d'architecture
ci-dessus : en plus de l'app mobile (TASK-S040), construire **aussi** un
téléphone logiciel pour ordinateur (desktop). Pas urgent, juste noter le
besoin pour plus tard — mêmes contraintes que TASK-S040 (SRTP obligatoire,
connexion "conventionnelle" par username complet, pas de champ domaine séparé
à comprendre par l'usager). Plateforme/techno pas encore scopée (Electron ?
app native Windows/Mac ? — à décider en même temps que TASK-S040 vu que les
deux partageront probablement la même logique SIP/SRTP sous-jacente).
Dépend de : TASK-S040 (même recherche de librairie SIP à faire une fois pour les deux).

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

### TASK-023.27 [x] Premier trunk PSTN réel (ScopServ, TLS) — bug contexte sipv-external
Demande de l'utilisateur (2026-07-24) : connecter un vrai compte SIP de son serveur
ScopServ (`vgw1.simpleip.scopcloud.com`, compte `15143222112`, DID de test qui lui
appartient) pour pouvoir tester de vrais appels entrants/sortants PSTN, sans pousser
de caller ID particulier. ScopServ reste pour l'instant la SEULE option de lignes
réelles (pas de trunk carrier direct SimpleIP). Confirmé par l'utilisateur : ce DID
sert uniquement à ses tests, pas de la production live.

⚠️ Bug découvert en cours de route : le profil sofia `external` utilisait
`context="public"`, qui collisionne avec le fichier statique vanilla
`dialplan/public.xml` (chargé par FreeSWITCH AVANT mod_xml_curl pour ce nom de
contexte) — exactement le même piège déjà rencontré et corrigé pour le profil
`internal` (TASK-S036). Un appel entrant réel via ce profil n'aurait jamais atteint
notre backend.
   Fix : contexte du profil `external` renommé `sipv-external` (même précédent que
   `sipv-internal`). `_handle_dialplan()` route `context in ("public", "sipv-external")`
   vers `_dialplan_public()`. `_dialplan_public()` prenait un `requested_context`
   codé en dur à `"public"` dans son XML de retour au lieu d'échoir le contexte
   RÉELLEMENT demandé — FreeSWITCH exige une correspondance exacte entre le contexte
   demandé et celui retourné (même règle déjà établie pour `_dialplan_internal`) ;
   sans ce fix, `sipv-external` aurait été rejeté comme "not found" malgré une
   réponse par ailleurs valide. Signature changée en
   `_dialplan_public(destination, db, requested_context="public")`, XML retourne
   `<context name="{requested_context}">`.

⚠️ Deuxième blocage : premier essai d'enregistrement en UDP simple → ScopServ
(Asterisk) répond `403 Forbidden` après un challenge digest pourtant correctement
calculé (3 tentatives, arrêtées volontairement pour ne pas déclencher un
anti-bruteforce sur le compte réel du client). L'utilisateur a confirmé de son côté :
compte configuré en TLS chez ScopServ, IP publique du serveur SIPV whitelistée.
   Fix : TLS activé sur le profil `external` (`external_ssl_enable=true`,
   `external_tls_port=5081`, `tls-cert-dir=$${external_ssl_dir}` — réutilise les
   certificats déjà en place pour le profil `internal`, `$${conf_dir}/tls`). Gateway
   reconfiguré avec `register-transport="tls"`, `proxy`/`register-proxy` pointant
   vers `vgw1.simpleip.scopcloud.com:5061` (port TLS standard côté ScopServ).
   Résultat confirmé en direct : `sofia status gateway t1001-gw-1e083163` →
   `State: REGED`, `Status: UP` — confirmé également visible côté ScopServ par
   l'utilisateur ("oui je te vois connecter").

Fait :
- `SIPTrunk.password` maintenant chiffré (Fernet, `app/core/crypto.py`) — jamais en
  clair en DB ni renvoyé par l'API (`TrunkOut.has_password: bool` remplace le champ
  mot de passe, même pattern que `ld_pin`/mots de passe admin téléphone).
  `create_trunk`/`update_trunk` chiffrent avant stockage.
- Enregistrements créés en DB (tenant t1001) : `SIPTrunk` "ScopServ Test"
  (`trunk_id=1e083163-f6f3-48c0-aff7-ff5e64fd9001`), `TenantDID` `15143222112`,
  `InboundRoute` (DID → extension `t1001-100`, pour test), `OutboundRoute`
  ("ScopServ test outbound", patterns `NXXNXXXXXX,1NXXNXXXXXX`, aucun strip/prepend).
- Fichier gateway FreeSWITCH créé à la main sur le serveur (config runtime
  FreeSWITCH, pas dans git) :
  `/usr/local/freeswitch/conf/sip_profiles/external/t1001-gw-1e083163.xml`.
- `vars.xml` et `sip_profiles/external.xml` modifiés en LIVE sur le serveur
  (192.168.1.55) pour activer TLS + renommer le contexte — sauvegardés avant
  modification (`external.xml.backup_pretrunk_20260724`,
  `vars.xml.backup_pretls_20260724`).

Écart vs plan : pas de génération dynamique de gateway via mod_xml_curl (section
`configuration`/`sofia.conf`) — le fichier gateway est écrit à la main sur le
serveur, comme le catalogue de modèles Grandstream (TASK-023.18) a dû être codé en
dur. Si plusieurs trunks/tenants doivent être ajoutés fréquemment à l'avenir, ça
vaudra la peine de rendre `sofia.conf` dynamique via xml_curl plutôt que de
continuer à écrire des fichiers à la main.

Reste à faire :
- Tester un vrai appel entrant sur le DID `15143222112` et un appel sortant réel
  depuis un poste t1001 (pas encore fait au moment d'écrire cette entrée).
- Router l'InboundRoute vers une destination définitive une fois les tests validés
  (actuellement pointé sur `t1001-100` par défaut).
- Portage de vrais DID de production PSTN (mentionné par l'utilisateur comme étape
  future, pas actuelle : "je vais transférer des DID pour tester avec le PSTN mais
  on est pas là encore").

Fichiers : sipv/backend/app/api/v1/endpoints/trunks.py,
api/v1/endpoints/xml_curl.py (+ script ponctuel de création DB, supprimé du serveur
après exécution). Config serveur (hors git) : `/usr/local/freeswitch/conf/vars.xml`,
`sip_profiles/external.xml`, `sip_profiles/external/t1001-gw-1e083163.xml`.

### TASK-S045 [x] Sync succursale (E911Address) + DID (TenantDID) depuis ERPCRM maître, ouverture des horaires en proxy
Pendant SIPV de TASK-023.30/TASK-023.31 (TASKERPCRM.md) -- voir ces entrées pour le
détail complet côté ERPCRM (modèles, UI, drag-and-drop). Ici seulement ce qui a changé
côté SIPV : ERPCRM devient maître pour `CompanySite`→`E911Address` et `DID`→`TenantDID`,
même patron bloquant que `sync_company` déjà en place.

Fait :
- `models/e911.py` : `E911Address.erpcrm_site_id` (UUID, unique, nullable).
- `models/sip.py` : `TenantDID.erpcrm_did_id` (UUID, unique, nullable) et
  `TenantDID.schedule_id` (FK `schedules.id`, `SET NULL`).
- `api/v1/endpoints/sync.py` : `POST /site` (upsert par `erpcrm_site_id`), `POST /did`
  (upsert par `erpcrm_did_id`, sinon adopte une ligne existante avec le même `number` --
  évite les doublons pendant la bascule des DID déjà présents).
- `api/v1/endpoints/dids.py` : `DELETE /{did_id}` passe de `get_current_user` à
  `get_current_user_or_service` pour qu'ERPCRM puisse supprimer réellement le miroir
  SIPV quand un DID est supprimé côté ERPCRM (avant : suppression impossible depuis
  ERPCRM, mirroir orphelin). `DESTINATION_TYPES` étendu (`fax`, `conference`,
  `transfer`, `message`).
- `api/v1/endpoints/schedules.py` : tous les endpoints (list/create/update/delete
  schedule, add/delete rule, list/create/delete holiday, check_is_open) passés de
  `get_current_user` à `get_current_user_or_service` (aucun n'utilisait le contenu de
  `user`, changement sûr) -- ERPCRM les proxy directement sans session utilisateur SIPV.
  Réutilise les modèles `Schedule`/`ScheduleRule`/`Holiday` déjà existants mais jamais
  utilisés (`models/schedule.py`) -- aucun nouveau modèle créé.
- Migrations `0051_e911_erpcrm_site_id` → `0052_tenant_did_erpcrm_id` →
  `0053_tenant_did_schedule_id`, appliquées sur le serveur distant.

Testé : sync succursale et DID vérifiés de bout en bout via l'API ERPCRM réelle (voir
TASK-023.30/.31), `alembic upgrade head` confirmé à `0053` sur le serveur distant,
`sipv-backend.service`/`sipv-backend-tls.service` redémarrés et `/api/health` vérifié
après chaque lot de déploiement (pas après chaque fichier individuel).
Fichiers : backend/app/models/e911.py, models/sip.py,
api/v1/endpoints/sync.py, dids.py, schedules.py,
alembic/versions/0051_e911_erpcrm_site_id.py → 0053_tenant_did_schedule_id.py.
Dépend de : TASK-S010.3, TASK-023.30/.31 (TASKERPCRM.md).

### TASK-S045.1 [x] Destination par plage horaire (ScheduleRule) + endpoint d'édition manquant
Pendant SIPV de TASK-023.31.1 (TASKERPCRM.md) -- voir cette entrée pour le
détail complet (UI, tests). Ici seulement le changement côté SIPV.

Fait :
- `models/schedule.py` : `ScheduleRule` += `destination_type`, `destination`
  (String(20)/String(100), nullable -- meme forme que `TenantDID`). Migration
  `0054_schedule_rule_destination.py`.
- `schedules.py` : `RuleOut`/`RuleCreate` transportent les 2 nouveaux champs ;
  nouveau `RuleUpdate` + `PUT /rules/{rule_id}` -- avant cette entrée, une
  règle ne pouvait qu'être créée ou supprimée, jamais modifiée en place, ce
  qui aurait forcé un delete+recreate côté ERPCRM pour le moindre changement.
  `/{sched_id}/is-open` renvoie maintenant aussi `destination_type`/
  `destination` de la règle qui matche (pas encore consommé nulle part --
  `xml_curl.py::_is_schedule_open` garde sa propre logique binaire dupliquée
  pour les ring groups, TASK-023.9, non touchée par cette entrée).

Testé : bout en bout via l'API ERPCRM réelle (voir TASK-023.31.1). Migration
appliquée sur le serveur distant (`alembic upgrade head` → `0054`),
`sipv-backend.service`/`sipv-backend-tls.service` redémarrés, `/api/health`
vérifié après coup.
Fichiers : backend/app/models/schedule.py, api/v1/endpoints/schedules.py,
alembic/versions/0054_schedule_rule_destination.py.
Dépend de : TASK-S045, TASK-023.31.1 (TASKERPCRM.md).

### TASK-S023.15.1 [x] Groupe de pickup nommé (PickupGroup) -- créer le groupe puis assigner les postes
Pendant SIPV de TASK-023.19.1 (TASKERPCRM.md) -- voir cette entrée pour le
détail complet (UI, tests). Ici seulement le changement côté SIPV.

Fait :
- `models/sip.py` : nouveau modèle `PickupGroup` (tenant_id, name, is_active)
  -- entité purement organisationnelle, **le dialplan (*8,
  `xml_curl.py::_pickup_dialplan_entries`, TASK-023.15, déjà en prod)
  continue de matcher par `SIPExtension.pickup_group` (string) -- non
  touché**, ce modèle sert seulement à pouvoir créer un groupe vide et le
  renommer/supprimer en masse sur ses membres, au lieu de dépendre d'au moins
  un poste taggé pour que le groupe "existe".
- `extensions.py` : `GET/POST /pickup-groups/tenant/{tenant_id}`,
  `PUT/DELETE /pickup-groups/{group_id}` -- renommer met à jour
  `SIPExtension.pickup_group` sur tous les membres (le nom EST la clé de
  matching côté dialplan) ; supprimer retire le tag (`None`) de tous les
  membres avant de supprimer la ligne, jamais de tag orphelin.
- Migration `0055_pickup_groups.py`.
- Endpoint existant `PUT /{ext_id}` (déjà TASK-023.22, `get_current_user_or_
  service`, `ExtUpdate` avec `pickup_group`/`can_intercept_calls`) inchangé
  -- réutilisé tel quel pour assigner/retirer un poste et le "Peut
  intercepter".

⚠️ Latent trouvé en testant (pas corrigé, hors scope de cette demande) :
`ExtUpdate.can_intercept_calls: bool | None` accepte `None` mais la colonne
DB est `NOT NULL` (`Boolean, default=True`) -- envoyer explicitement `null`
plante en 500 (IntegrityError) au lieu d'un 422 propre. Aucun appelant actuel
(ERPCRM inclus) n'envoie jamais `null` pour ce champ, donc pas de risque en
usage normal ; à corriger si ça revient (retirer `| None` ou ignorer les
`None` explicites pour ce champ précis dans `update_extension`).

Testé : bout en bout via l'API ERPCRM réelle (voir TASK-023.19.1). Migration
appliquée sur le serveur distant, services redémarrés, `/api/health` vérifié.
Fichiers : backend/app/models/sip.py, models/__init__.py,
api/v1/endpoints/extensions.py, alembic/versions/0055_pickup_groups.py.
Dépend de : TASK-S023.15, TASK-023.19.1 (TASKERPCRM.md).

#### TASK-S057 [x] Provisioning -- SIP transport (TLS/TCP) jamais poussé dans la config XML du téléphone

Découvert par l'utilisateur (2026-08-11) en testant un appel bidirectionnel
102↔103 : le 103 (GXP2170, poste réel de l'utilisateur, compte 3) ne
recevait pas d'appels entrants tant que son "SIP Transport" restait en UDP
(config héritée de son ancien UCM). Une fois changé manuellement en TLS/TCP
sur le téléphone, les appels fonctionnent dans les deux sens.

Cause supposée à l'époque : "rien dans le générateur de provisioning
(`api/v1/endpoints/provisioning.py`) ne pousse ce champ dans le XML de
config du téléphone" -- **cette conclusion était fausse**, trouvée en
grep-ant seulement le code Python de l'endpoint, pas le contenu réel du
`config_template` (stocké en DB, pas dans le dépôt).

**Vérifié en conditions réelles (2026-08-16, boucle autonome)** : requête
directe contre la DB SIPV en production -- le `config_template` du
`PhoneModel` GXP2135 (le seul modèle avec un template réel ; GXP2130/2140/
2160/2170 restent volontairement vides, voir TASK-S011.4 -- tous les postes
réels et de test, dont le poste physique 103, sont provisionnés sous ce
modèle GXP2135 peu importe le hardware réel) contient déjà, depuis le
**2026-08-02** (TASK-S011.4, "premier vrai config_template GXP2135
écrit") :
```
<P130>{{ {'udp': 0, 'tcp': 1, 'tls': 2}.get(extension.transport, 2) }}</P130>
<P2329>{{ 1 if extension.transport == 'tls' else 0 }}</P2329>
```
Alimenté dynamiquement par `SIPExtension.transport` (`tls` par défaut),
exactement ce que cette tâche demandait. TASK-S057 a donc été ouverte
(2026-08-11) 9 jours APRÈS que ce câblage existait déjà -- doublon non
détecté au moment de la création (voir la procédure de grep par mots-clés
dans `feedback_workflow_rules`, pas suivie à l'époque).

**Cause réelle du symptôme original (103 en UDP malgré le template déjà
dynamique)** : pas un manque de câblage, mais que le téléphone physique 103
n'avait pas re-tiré sa config depuis SIPV après le 2026-08-02 (config
héritée de l'ancien UCM, jamais re-provisionnée automatiquement). Comment
un téléphone neuf apprend l'URL de provisioning SIPV au tout premier
démarrage (DHCP option 66 vs configuration manuelle unique) reste une
question ouverte -- **c'est TASK-S011.4** (toujours `[~]`, décision
explicite à trancher avec Philippe, non ré-ouverte ici, pas de scope
nouveau ajouté).

Aucun changement de code nécessaire -- correction de la documentation
seulement, le comportement en production était déjà correct.

#### TASK-S058 [x] Bug -- Hold GXP2170/GXP2135 raccrochait l'appel au lieu de le mettre en attente (rejet SRTP sur re-INVITE)

Testé par l'utilisateur avec un vrai appel bidirectionnel 103 (GXP2170,
compte 3, poste réel) ↔ 102 (GXP2135) -- une fois le problème de transport
(TASK-S057) réglé, l'appel fonctionne des deux côtés, MAIS appuyer sur
Hold sur le GXP2170 raccrochait l'appel au lieu de le mettre en attente.
Hypothèse initiale (touche Hold mal mappée / config héritée de l'ancien
UCM) **infirmée** par un `sofia siptrace` capturé pendant un vrai appel :
le GXP2170 envoie un re-INVITE de Hold parfaitement standard (`a=sendonly`),
mais FreeSWITCH le **rejette avec `488 Not Acceptable Here`**
(`Crypto not negotiated but required` / `Reinvite resulted in codec
negotiation failure`, `switch_core_media.c:5604`) parce que l'offre SDP du
Hold ne réoffre aucune ligne `a=crypto`, alors que `rtp_secure_media` était
forcé à `mandatory` pour TOUTES les extensions sans exception
(`xml_curl.py`, `_user_xml`). Reproduit à l'identique sur le GXP2135 (102)
-- donc pas un problème spécifique au GXP2170, ni une config héritée de
l'ancien UCM.

**Corrigé** : ajout de la variable directory `execute_on_answer` =
`set:rtp_secure_media=optional`, qui ne s'applique qu'une fois l'appel
répondu (le SRTP reste `mandatory`, donc obligatoire, pour ÉTABLIR
l'appel) -- les renégociations SDP ultérieures (Hold, etc.) acceptent le
SRTP s'il est réoffert, sans l'exiger. Mécanisme natif FreeSWITCH
(`switch_channel.c:3896`, `SWITCH_CHANNEL_EXECUTE_ON_ANSWER_VARIABLE`),
aucun patch du code source FreeSWITCH.

⚠️ Incident pendant le déploiement (corrigé dans la foulée) : le premier
correctif incluait un commentaire XML explicatif dans le XML `<variables>`
retourné par `_user_xml` -- un commentaire XML ne peut jamais contenir
`--`, ce que ce commentaire faisait (utilisé comme tiret de ponctuation),
ce qui rendait le XML de la réponse `directory` invalide
(`switch_xml.c:1797`, `unclosed <!--`) et a fait échouer TOUS les REGISTER
(tous les postes "down") jusqu'au correctif (commentaire retiré du XML
émis, gardé seulement en commentaire Python au-dessus). Backend redémarré
et validé (`/api/health` + re-registration confirmée) après le correctif.

Fichiers : `backend/app/api/v1/endpoints/xml_curl.py` (`_user_xml`).
Déployé directement sur le serveur (`/home/sipv/sipv/...`) -- **⚠️ ce
dépôt local et le serveur ont un écart important** (dépôt local très en
retard sur ce qui tourne réellement, voir `git status` -- à réconcilier
un jour, hors scope de cette tâche).

##### TASK-S058.1 [x] Keep-alive NAT serveur aligné sur les téléphones (20s)

Demande de l'utilisateur après coup : les téléphones Grandstream ont un
"Keep-Alive Interval" par défaut à 20s (paquet de garde NAT côté client),
mais FreeSWITCH n'envoyait aucun ping NAT de son côté
(`nat-options-ping` et `all-reg-options-ping` étaient commentés dans le
profil sofia `internal`). Activé `nat-options-ping=true` +
`ping-mean-interval=20` dans
`/usr/local/freeswitch/conf/sip_profiles/internal.xml` (fichier serveur
manuel, pas généré par SIPV, pas dans ce dépôt) pour que FreeSWITCH
rafraîchisse aussi le mapping NAT du routeur toutes les 20s, en phase avec
les téléphones. XML validé (`xml.dom.minidom`) avant application cette
fois -- backup du fichier pris avant modif. `reloadxml` +
`sofia profile internal restart` appliqués, `102`/`103` confirmés toujours
enregistrés et `Ping-Status: Reachable` après coup.

##### TASK-S058.2 [x] Kamailio (SBC, TASK-S039) jamais validé avec vrais téléphones -- 3 bugs trouvés et corrigés

Session de test réelle (2026-08-11/12, 102/103 physiques) : le cutover
Kamailio du 2026-07-23 (TASK-S039) n'avait jamais été testé avec un vrai
appel/audio (documenté explicitement comme hors scope à l'époque). Trois
bugs distincts trouvés en conditions réelles :

1. **Coupure d'appel automatique après ~32s** -- `ext-sip-ip` du profil
   `internal` (FreeSWITCH) pointait encore vers l'IP publique externe
   (`142.112.42.52`, via `$${external_sip_ip}`), alors que ce profil
   écoute maintenant en loopback (`sip-ip=127.0.0.1`) derrière Kamailio.
   Le téléphone recevait donc un `Contact` externe dans le `200 OK`, son
   ACK partait vers cette IP publique (confirmé : Kamailio le relayait
   bien là, mais rien n'y écoute), FreeSWITCH ne recevait jamais l'ACK,
   retransmettait le `200 OK` ~10x puis abandonnait (`408 ACK Timeout`)
   après ~32s pile. Diagnostiqué avec siptrace FreeSWITCH + `journalctl`
   Kamailio (`corex.debug 4` en direct, sans redémarrage) croisés sur le
   même Call-ID. Corrigé : `ext-sip-ip` retiré du profil `internal`
   uniquement (`external`/trunks gardent l'IP publique, inchangé) --
   FreeSWITCH retombe sur `sip-ip=127.0.0.1`, que Kamailio sait relayer.
2. **`auth-calls` du profil `internal` jamais réellement actif** --
   référençait `$${internal_auth_calls}`, jamais défini dans `vars.xml`
   (résolvait vide/false). Sans authentification challengée sur les
   INVITE entrants (pas juste le REGISTER), FreeSWITCH ne faisait jamais
   de requête `directory` pour peupler les variables custom
   (`hold_music`, `effective_caller_id_name`, etc.) sur le canal
   APPELANT -- cause du mauvais nom affiché ET du MOH par défaut joué au
   lieu de celui du tenant selon qui faisait le Hold. Corrigé : ajout de
   `internal_auth_calls=true` dans `vars.xml`.
3. **Voix silencieuse au début de CHAQUE appel jusqu'au premier Hold** --
   plusieurs fausses pistes explorees avant la vraie cause (port RTP qui
   change = normal, `rtp_secure_media=optional` = pas la cause principale
   meme si passe a `forbidden` en cours de route). VRAIE CAUSE, prouvee de
   facon definitive : **rtpengine reecrit le SDP et alloue ses PROPRES
   ports media**, jamais annonces par FreeSWITCH -- confirme avec
   `rtpengine-ctl list sessions <call-id>` montrant un port (ex: `30516`)
   alloue par rtpengine cote telephone, absent de tous les logs
   FreeSWITCH. Contredit la doc du 2026-07-23 (TASK-S039) qui disait
   `rtpengine_manage()` desactive/jamais teste avec audio reel -- l'appel
   etait pourtant bien ACTIF dans `kamailio.cfg` au moment de cette
   session (le daemon `rtpengine-daemon.service` tourne depuis un reboot
   du 2026-08-11 06h58, mais QUAND le script Kamailio a commence a
   l'appeler reellement n'est pas confirme -- possiblement des la
   migration meme, mal redocumente). Corrige : `rtpengine_manage()`
   recommente dans `kamailio.cfg` (backup pris), retour au media direct
   telephone<->FreeSWITCH. `kamailio -c -f ...` valide avant restart du
   service. Note pour tout debug audio futur sur ce serveur : toujours
   verifier `rtpengine-ctl list sessions all` en premier reflexe --
   composant facile a oublier puisqu'il n'apparait dans aucun log
   FreeSWITCH.

Tous ces fichiers (`internal.xml`, `vars.xml`, `kamailio.cfg`) sont des
fichiers SERVEUR manuels, PAS générés par SIPV, PAS dans ce dépôt --
backups pris avant chaque modif (`.bak-<date>`), XML validé avant chaque
`reloadxml`/restart de profil.

##### TASK-S058.3 [x] MOH -- mauvais fichier sélectionné pour le tenant + reprise de position par appel en cours

Découvert en même temps : le fichier MOH qui jouait ("Arianne", une voix,
pas de la musique) n'était PAS un bug SIP -- c'est `test_moh_24k` (fichier
de test, même ID que les phrases-prompt 24kHz testées plus tôt) qui était
sélectionné (`TenantMohSelection`) pour le tenant au lieu de "decontract"
(le vrai MOH voulu). Corrigé en base + `regenerate_tenant_moh_stream()`
rappelé -- "decontract" joue maintenant.

Comportement de reprise MOH demandé : le MOH doit garder sa position PAR
APPEL EN COURS -- si on remet en Hold plusieurs fois le même appel, ça
reprend où c'était rendu (pas depuis le début à chaque fois), mais un
NOUVEL appel repart toujours à zéro. Chaque poste doit avoir son propre
suivi, indépendant des autres.

Vérifié dans le code source FreeSWITCH (`switch_core_media.c`,
`switch_ivr.c`) avant de coder quoi que ce soit : aucune mémoire de
position native -- chaque Hold relance `switch_ivr_broadcast()` depuis
le début, l'Unhold arrête juste le broadcast sans rien sauvegarder.
Mécanisme de contournement identifié et PROUVÉ manuellement en direct
(postes 102/103, `uuid_setvar`/`uuid_getvar`) avant tout code :
- FreeSWITCH pose `playback_last_offset_pos` sur le canal qui JOUE la
  MOH (le partenaire du poste qui a fait Hold) dès que la lecture
  s'arrête, normale ou interrompue (`switch_ivr_play_say.c:2014`,
  inconditionnel).
- L'application `playback::` accepte `fichier.wav@@<sample>` pour
  reprendre exactement à cette position (`mod_dptools`).
- `hold_music` est relu dynamiquement à chaque nouveau Hold -- le
  mettre à jour entre deux Hold suffit à faire reprendre le suivant au
  bon endroit.
- Test manuel : Hold ~10s, lecture de `playback_last_offset_pos` sur le
  partenaire (147680), ré-application via `uuid_setvar` sur le poste en
  Hold, nouveau Hold -- reprise exacte confirmée par l'utilisateur.

Automatisé dans `app/core/moh_hold_tracker.py` (nouveau service, démarré
dans le `lifespan` de `main.py` à côté du client ESL existant) : une
connexion ESL dédiée (event stream, lecture seule, différente de la
connexion commande/réponse partagée `get_esl()`) écoute `CHANNEL_HOLD` /
`CHANNEL_UNHOLD` / `CHANNEL_HANGUP_COMPLETE`. Le partenaire est lu
directement depuis le header `Other-Leg-Unique-ID` de l'événement
(confirmé présent en direct via une sonde ESL avant de coder). État
gardé en mémoire, keyé par UUID du poste qui fait Hold -- jamais
persisté : un nouvel appel = nouveaux UUID = aucune entrée = repart à
zéro, sans code supplémentaire pour ce cas.

Limite connue et acceptée : en mode Liste (plusieurs pistes chaînées
via `file_string`), si un cycle de Hold dépasse la durée du fichier en
cours, FreeSWITCH n'expose aucun moyen de savoir quel fichier de la
chaîne était ouvert à l'arrêt -- la reprise suivante cible le même
fichier avec l'offset lu. En mode Aléatoire (un seul fichier par appel),
ce cas ne se produit pas. Échec silencieux en cas de valeur
incohérente : l'appel retombe sur le comportement par défaut (recommence
au début), jamais une lecture corrompue.

Point mineur connu, sans impact fonctionnel : `sipv-backend` tourne en
plusieurs workers uvicorn, donc le tracker démarre une fois par worker
(2 connexions ESL dédiées vues dans `ss -tnp`) -- redondant (les deux
calculent le même résultat) mais pas incorrect.

Testé et confirmé par l'utilisateur en direct (postes 102/103, plusieurs
cycles Hold/Unhold consécutifs sur le même appel) : la MOH reprend
progressivement où elle était rendue à chaque Hold, et un nouvel appel
repart bien à zéro.

##### TASK-S058.4 [x] MOH -- `local_stream://` retiré, remplacé par `file_string://` (réinitialisation à zéro à chaque appel)

Bug architectural : `hold_music` pointait vers `local_stream://{tenant}`
(flux continu partagé, pensé pour une "radio IP" -- rejoint toujours en
cours de lecture, ne redémarre jamais à zéro). Ça faussait tout le
troubleshooting Hold précédent (TASK-S058/S058.1/S058.2) : le problème
"la MOH ne redémarre pas à zéro sur un nouvel appel" persistait malgré
tous les fix SIP/crypto/kamailio, parce que la config MOH elle-même
était la mauvaise architecture depuis le départ.

Fix dans `xml_curl.py` (`_user_xml`) : `hold_music` construit maintenant
en lisant directement les fichiers `.wav` du dossier
`MOH_SOUNDS_BASE/{domain}/` (déjà synchronisé par
`regenerate_tenant_moh_stream()`, triés par préfixe numérique =
`sort_order`) et en chaînant via `file_string://` (redémarre bien à
zéro à chaque `playback()`, vérifié dans le code source FreeSWITCH).
Mode liste (`moh_shuffle=False`) : chaîne tous les fichiers dans l'ordre.
Mode aléatoire (`moh_shuffle=True`) : un seul fichier choisi au hasard,
re-tiré à chaque REGISTER. Le `silence_stream://500!` de tête (0.5s,
TASK antérieure) est conservé devant la chaîne.
`local_stream://` n'est plus utilisé nulle part pour `hold_music`.

Déployé et vérifié par curl direct sur `/api/v1/xml_curl` (section
directory, REGISTER t1001-102) : `hold_music` retourne bien
`file_string://silence_stream://500!/usr/local/freeswitch/sounds/sipv_moh/t1001/000_....wav`,
fichier confirmé lisible par l'utilisateur `freeswitch`.
Confirmé par test réel sur téléphone (2 appels distincts, chacun mis en
Hold séparément) : la MOH repart du tout début à chaque fois, aucune
reprise d'un appel à l'autre.

Reprise de position par appel en cours = toujours TASK-S058.3, non
implémenté, distinct de ce fix.

### TASK-S059 [x] Backup cloud automatique de notre propre infra SIPV (pas client) -- réglages page "Serveur"

⚠️ Ne pas confondre avec TASK-S012.1 (stockage cloud du CLIENT pour ses
enregistrements d'appel, service payant). Ici c'est NOTRE backup interne du
serveur SIPV (DB + config + MOH) vers un cloud (Dropbox/OneDrive/Google
Drive). Cross-ref ERPCRM : TASK-035 (TASKERPCRM.md), voir ce fichier pour la
vision complète donnée par Philippe le 2026-08-13.

Côté SIPV : page "Serveur" du portail -- réglages de connexion cloud +
bouton de backup, avec un fichier de connexion/config SÉPARÉ de celui
d'ERPCRM (pas de credentials partagés). Contenu du backup SIPV : dump DB +
config serveur (kamailio.cfg, internal.xml, vars.xml, certs TLS) + MOH.
Backup récurrent activable indépendamment d'ERPCRM, rotation en générations
(ex. 3 mois, la plus ancienne s'écrase), fréquence/rétention à définir via
sélecteur (1 jour/1 sem/1 mois/2 mois/3 mois -- portée du réglage encore à
clarifier, voir questions ouvertes dans TASK-035 ERPCRM).

**Décision 2026-08-13** : fournisseurs retenus pour tester = Dropbox ET Google
Drive (voir TASK-035 ERPCRM pour le détail -- même décision, double backup ou
failover si les deux sont connectés, encore à trancher).

**Design confirmé 2026-08-13** : voir TASK-035 (TASKERPCRM.md) pour le détail
complet -- même mécanique côté SIPV (page "Serveur") : double backup
Dropbox+Google, un seul dump par run, cycles entièrement configurables
(bouton "Ajouter un cycle", type de fréquence + case "générations" avec
compte éditable, défaut 3), bande passante configurable, fichier de
connexion cloud séparé de celui d'ERPCRM.

**Précision 2026-08-13** : serveur SIPV tourne en UTC (`Etc/UTC`). Design
final identique à TASK-035 (ERPCRM) : fuseau + heure de déclenchement +
limite de bande passante réglés PAR CLOUD (Dropbox et Google Drive séparés),
pas un seul réglage projet. Le cycle (fréquence/jour/rétention) reste
défini une fois par projet, partagé par les deux clouds.

Design considéré COMPLET, prêt pour plan technique final et GO d'implémentation.

**GO reçu 2026-08-15 -- implémenté.** Architecture retenue : SIPV n'a pas de
domaine public joignable par Dropbox/Google -- le flux OAuth est donc RELAYÉ
par ERPCRM (seul serveur avec `https://portail.simpleip.tel`). ERPCRM ne
reçoit/relaie que `code`+`state` (jamais le client_secret de SIPV, qui reste
exclusivement sur SIPV).

Fichiers touchés côté SIPV :
- `backend/app/models/backup.py` (CloudBackupConnection avec `oauth_state`
  directement sur la ligne -- pas d'AppSetting générique côté SIPV, contrairement
  à ERPCRM ; BackupCycle, BackupRunLog) + import dans `models/__init__.py`
- Migration `alembic/versions/0061_backup_tables.py` (convention SIPV :
  fichiers numérotés manuels, pas autogenerate)
- `backend/app/core/config.py` -- ajout DROPBOX_CLIENT_ID/SECRET,
  GOOGLE_CLIENT_ID/SECRET (fallback optionnel), ERPCRM_PUBLIC_BASE_URL (pour
  construire le redirect_uri OAuth pointant vers ERPCRM)
- `backend/app/core/backup_cloud.py` -- quasi identique à la version ERPCRM
  (OAuth + upload throttlé Dropbox/Google Drive), dossier cloud `SIPV_Backups`
- `backend/app/workers/backup_runner.py` -- un seul `pg_dump` (DB `sipv`) +
  tar par exécution : `.env`, `certs/`, unités systemd `sipv-backend*.service`,
  `/etc/kamailio/kamailio.cfg`, `/etc/freeswitch/vars.xml`,
  `/etc/freeswitch/conf/local_stream/`, MOH réel
  (`/usr/local/freeswitch/sounds/sipv_moh_backups/`). PAS les enregistrements
  d'appel (`recordings/`, hors scope, sujet TASK-S012.1/TASK-034 ERPCRM séparé).
  Rotation par préfixe `sipv_{frequence}_{date}.tar.gz`. Anti-boucle : une
  tentative par jour par connexion (même fix que le bug ERPCRM du 2026-08-14).
- `backend/app/services/backup_poller.py` (nouveau dossier `services/`) --
  poller asyncio in-process, démarré dans `main.py` lifespan
- `backend/app/api/v1/endpoints/backup.py` -- CRUD connexions/cycles,
  `GET /connections/{provider}/connect-url` (retourne l'URL au lieu de
  rediriger -- c'est ERPCRM qui redirige le navigateur),
  `POST /connections/{provider}/callback` (reçoit code+state relayés par
  ERPCRM, fait l'échange réel ici). Auth `get_current_user_or_service` partout.
- Dépendances ajoutées au venv + `requirements.txt` :
  `google-api-python-client`, `google-auth`, `google-auth-httplib2`

Fichiers touchés côté ERPCRM (proxy, voir aussi TASK-035) :
- `backend/app/core/sipv_client.py` -- fonctions proxy (list/update
  connexions, credentials, connect-url, relay_backup_callback, cycles CRUD,
  run, logs)
- `backend/app/api/v1/endpoints/server.py` -- routes `/api/v1/server/backup/*`.
  `connect`/`callback` volontairement SANS authentification JWT (navigation
  directe du navigateur après redirection Dropbox/Google, pas un appel XHR du
  SPA -- CSRF protégé par le `state` côté SIPV, pas par un token ici)
- `frontend/src/pages/Server.jsx` -- nouvelle section "Backup cloud SIPV"
  (mêmes composants que Admin.jsx côté ERPCRM : cartes connexion, cycles,
  bouton backup manuel, historique), gère `?server_backup=...` dans l'URL,
  onglets "Téléphonie"/"Backup cloud" ajoutés en haut de la page (2026-08-16)

Vérifié en conditions réelles (pas juste imports) :
- `_build_dump()` testé directement sur SIPV -- tous les fichiers de config
  présents dans l'archive (kamailio.cfg, vars.xml, local_stream, MOH, certs,
  .env, unités systemd)
- Chaîne proxy ERPCRM→SIPV testée directement -- réponse reçue avec succès
- Dropbox connecté et backup manuel réussi (`sipv_daily_2026-08-16.tar.gz`),
  cycles daily/weekly/monthly configurés et actifs
- Services redémarrés des deux côtés, tous vérifiés actifs

**Incident 2026-08-16** : découverte que le dépôt GitHub `CaptainePoui/SIPV`
(poussé le 2026-08-12) l'était depuis un MIROIR du code SIPV conservé sur le
disque d'ERPCRM (`/home/simpleip/sipv`), pas depuis le vrai serveur SIPV --
qui n'a jamais eu de clé SSH GitHub. Ce miroir était donc périmé (aucun
changement depuis le 12 août, alors que tout le travail de cette session a
été déployé directement sur le vrai serveur par SSH). Resynchronisé par
rsync (serveur réel -> miroir), MAIS un premier rsync avec `--delete` a
supprimé par erreur des fichiers qui n'existaient QUE dans le miroir
(CLAUDE.md, TASKSIPV.md, frontend/.env -- jamais déployés sur le serveur
réel). Restaurés : CLAUDE.md et frontend/.env via `git checkout` (identiques
à la dernière version commitée, aucune perte). TASKSIPV.md a dû être
reconstruit manuellement (les ajouts de cette session, dont cette section-ci,
n'étaient pas encore commit --  reconstruits depuis l'historique de la
conversation, pas depuis git). Vérifié par dates de modification réelles sur
le serveur SIPV (`find -newer`) : aucun fichier touché entre le 12 août
12h43 et cette session -- confirme qu'aucune session intermédiaire n'a été
perdue, seul le rattrapage de CETTE session était nécessaire.

Miroir rattrapé et repoussé (`bc50f73`), mais Philippe a explicitement
rejeté cette approche (2026-08-16) : SIPV doit être autonome vis-à-vis
d'ERPCRM, d'autant plus qu'il va changer de serveur bientôt (voir mémoire
`project_server_migration_planned`). Remplacement en cours : accès Git
DIRECT depuis le serveur SIPV lui-même (`git@github.com:CaptainePoui/SIPV.git`),
clé de déploiement dédiée déjà générée sur SIPV
(`~/.ssh/id_ed25519_github`), en attente que Philippe l'ajoute comme Deploy
Key (accès écriture) sur GitHub avant de finaliser (`git init` local déjà
fait, remote déjà configuré, reste `git fetch` + `git reset origin/main`
une fois la clé autorisée).

**État final 2026-08-16** : Dropbox ✓ connecté et testé (voir plus haut).
Google Drive -- reporté par choix explicite de Philippe ("je n'activerai
pas l'API Google de suite"), pas un blocage technique, code déjà prêt.
