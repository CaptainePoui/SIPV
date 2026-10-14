"""Touches et boutons sous l'ecran des Grandstream GXP21xx (2026-10-14, TASK-051).

Seule source : gabarits officiels du firmware 1.0.11.106 fournis par Philippe
(~/GrandStream/Template_Config_Pcode/config-template/gxp2130_40_60_70_35_config_1.0.11.106.txt pour les touches,
..._config_alias_1.0.11.106.xml pour les boutons sous l'ecran). Rien de devine : chaque code vient de ces fichiers.
"""

# Touches a cote de l'ecran (VPK) :
# - touche n <= 6 : mode P1363+2(n-1), compte P1364+2(n-1), description P1465+2(n-1), valeur P1466+2(n-1) ;
# - touche n >= 7 : P23800+4(n-7) (+0 mode, +1 compte, +2 description, +3 valeur).
# Regle verifiee touche par touche pour les 5 modeles. (fixes, total) : les touches fixes sont les touches physiques
# (page 1) ; les dynamiques forment les pages suivantes, 8 par page sur l'ecran.
GS_VPK_LAYOUT = {"GXP2130": (3, 12), "GXP2140": (4, 16), "GXP2160": (6, 24), "GXP2135": (8, 32), "GXP2170": (12, 48)}
VPK_KEYS_PER_PAGE = 8

# Modes, legende des touches fixes du gabarit. Une touche dynamique prend le meme code moins 10 (legende « Dynamic VPK »)
# et n'accepte ni Ligne ni Ligne partagee. (L'ancienne table appliquait la legende fixe aux touches dynamiques :
# Parcage 19 = « Information », Parcage surveille 26 = « Verrouillage clavier » -- corrige le 2026-10-14.)
GS_KEY_MODES = {
    "none": -1, "line": 0, "shared_line": 1, "speed_dial": 10, "blf": 11, "presence_watcher": 12, "eventlist_blf": 13,
    "speed_dial_active": 14, "dial_dtmf": 15, "voicemail": 16, "call_return": 17, "transfer": 18, "park": 19,
    "intercom": 20, "ldap_search": 21, "conference": 22, "paging": 23, "record": 24, "call_log": 25,
    "park_retrieve": 26, "menu": 27, "xml_app": 28, "information": 29, "message": 30, "forward": 31, "dnd": 32,
    "redial": 33, "instant_messages": 34, "multicast_listen": 35, "keypad_lock": 36,
    # Fonctions SIPV sans mode Grandstream propre : BLF sur la file, sinon numerotation rapide du code de fonction
    "queue": 11, "agent_login": 10, "agent_logout": 10, "agent_pause": 10, "pickup_group": 10, "feature_code": 10,
    "door": 10,
}
# Libelles des menus deroulants (ordre de la liste du gabarit)
GS_KEY_MODE_LABELS = [
    ("none", "Aucune"), ("line", "Ligne"), ("shared_line", "Ligne partagée"), ("speed_dial", "Numérotation rapide"),
    ("blf", "BLF (voyant d'un poste)"), ("presence_watcher", "Présence"), ("eventlist_blf", "Liste BLF"),
    ("speed_dial_active", "Numérotation rapide (compte actif)"), ("dial_dtmf", "Envoyer DTMF"),
    ("voicemail", "Messagerie vocale"), ("call_return", "Rappeler le dernier appel"), ("transfer", "Transfert"),
    ("park", "Parcage"), ("intercom", "Intercom"), ("ldap_search", "Recherche LDAP"), ("conference", "Conférence"),
    ("paging", "Diffusion (multicast paging)"), ("record", "Enregistrement"), ("call_log", "Journal d'appels"),
    ("park_retrieve", "Parcage surveillé"), ("menu", "Menu"), ("xml_app", "Application XML"),
    ("information", "Information"), ("message", "Message"), ("forward", "Renvoi"), ("dnd", "Ne pas déranger"),
    ("redial", "Recomposer"), ("instant_messages", "Messages instantanés"), ("multicast_listen", "Écoute multicast"),
    ("keypad_lock", "Verrouillage clavier"),
]
FIXED_ONLY_MODES = {"line", "shared_line"}


def vpk_pcodes(n: int) -> tuple[int, int, int, int]:
    if n <= 6:
        return 1363 + 2 * (n - 1), 1364 + 2 * (n - 1), 1465 + 2 * (n - 1), 1466 + 2 * (n - 1)
    base = 23800 + 4 * (n - 7)
    return base, base + 1, base + 2, base + 3


def vpk_keys(buttons, model_name: str | None) -> list[dict]:
    """Toutes les touches du modele, dans l'ordre (le gabarit : une touche dynamique, meme « aucune », doit etre envoyee
    a sa place). Philippe (2026-10-14) : une page non ajoutee = ses touches a « aucune » -- sinon le telephone garde
    ses anciens reglages."""
    fixed, total = GS_VPK_LAYOUT.get((model_name or "").upper(), (0, 0))
    by_index = {(b.page or 0) * VPK_KEYS_PER_PAGE + b.position: b for b in buttons}
    out = []
    for n in range(1, total + 1):
        b = by_index.get(n)
        mode = GS_KEY_MODES.get(b.button_type, -1) if b else -1
        if n > fixed and mode != -1:
            mode = mode - 10 if mode >= 10 else -1          # Ligne / Ligne partagee impossibles sur une touche dynamique
        pm, pa, pd, pv = vpk_pcodes(n)
        out.append({"n": n, "p_mode": pm, "p_account": pa, "p_label": pd, "p_value": pv, "mode": mode,
                    "account": (b.sip_account_index - 1) if b and mode != -1 else 0,
                    "label": (b.label or "") if b and mode != -1 else "",
                    "value": (b.value or b.destination or "") if b and mode != -1 else ""})
    return out


def merge_keys(template_items, phone_buttons) -> list:
    """Touches du modele de provisionnement, puis ajustements du poste : une touche du poste remplace celle du modele a la
    meme place (une touche « aucune » du poste efface celle du modele). Philippe (2026-10-14) : « on garde la possibilite
    d'ajuster une option ou une touche par-dessus son modele »."""
    by_index = {((i.page or 0), i.position): i for i in template_items}
    for b in phone_buttons:
        by_index[((b.page or 0), b.position)] = b
    return list(by_index.values())


# Boutons sous l'ecran (softkeys), gabarit « alias » (noms au lieu de P-codes).
SOFTKEY_IDLE_COUNT = 3        # pks.softkey.1-3 (ecran au repos)
SOFTKEY_CALL_COUNT = 3        # pks.scSoftkey.1-3 (ecran pendant un appel)
SOFTKEY_IDLE_MODES = [("Default", "Par défaut"), ("SpeedDial", "Numérotation rapide"),
                      ("SpeedDialViaActiveAccount", "Numérotation rapide (compte actif)"), ("VoiceMail", "Messagerie vocale"),
                      ("CallReturn", "Rappeler le dernier appel"), ("Intercom", "Intercom"), ("LDAPSearch", "Recherche LDAP"),
                      ("CallLog", "Journal d'appels"), ("Menu", "Menu"), ("Information", "Information"),
                      ("Message", "Message")]
SOFTKEY_CALL_MODES = [m for m in SOFTKEY_IDLE_MODES if m[0] != "Menu"]
# Boutons systeme de l'ecran au repos qu'on peut cacher (softkeys.state.idle.hideSystemKeys)
SOFTKEY_IDLE_SYSTEM = ["Next", "History", "ForwardAll", "Redial"]
# Disposition des boutons par etat d'appel : (nom de l'element, libelle, options possibles, valeur par defaut du gabarit)
SOFTKEY_STATES = [
    ("inDialing", "En composition",
     "BTPhonebook,BTOnOff,EndCall,ReConf,ConfRoom,Redial,Dial,Backspace,PickUp,Target",
     "BTPhonebook,BTOnOff,EndCall,ReConf,ConfRoom,Redial,Dial,Backspace,PickUp,Target"),
    ("inOnhookDialing", "Composition combiné raccroché",
     "BTPhonebook,DirectIP,Onhook,Cancel,Dial,Backspace,Target",
     "BTPhonebook,DirectIP,Onhook,Cancel,Dial,Backspace,Target"),
    ("InRinging", "Ça sonne", "Answer,Reject,Forward,ReConf,Custom-Silence", "Answer,Reject,Forward,ReConf"),
    ("inCalling", "Appel en cours de composition", "BTOnOff,Cancel,EndCall,ReConf,ConfRoom,ConfCall",
     "BTOnOff,Cancel,EndCall,ReConf,ConfRoom,ConfCall"),
    ("inCallConnected", "En appel",
     "BTPhonebook,BTOnOff,EndCall,ReConf,ConfRoom,Custom-Confcall,Cancel,NewCall,Swap,Transfer,Trnf>VM,DialDTMF,"
     "BSCCenter,URecord,Record,UCallPark,PrivateHold,CallPark,Custom-Hold,Custom-Conference,Custom-Mute",
     "BTPhonebook,BTOnOff,EndCall,ReConf,ConfRoom,Custom-Confcall,Cancel,NewCall,Swap,Transfer,Trnf>VM,DialDTMF,"
     "BSCCenter,URecord,Record,UCallPark,PrivateHold,CallPark"),
    ("inConferenceConnected", "En conférence",
     "BTOnOff,EndCall,Kick,NewCall,Trnf>VM,DialDTMF,BSCCenter,URecord,Record,ConfRoom,Add,Custom-Hold,Custom-Split,Custom-Mute",
     "BTOnOff,EndCall,Kick,NewCall,Trnf>VM,DialDTMF,BSCCenter,URecord,Record,ConfRoom,Add"),
    ("inOnhold", "En garde", "ReConf,Resume,HoldTrnf,ConfCall,Add,Custom-NewCall,Custom-EndCall",
     "ReConf,Resume,HoldTrnf,ConfCall,Add"),
    ("inCallFailed", "Appel échoué", "EndCall,ReConf,ConfRoom,Custom-NewCall", "EndCall,ReConf,ConfRoom"),
    ("inTransfer", "En transfert", "BTOnOff,Cancel,BlindTrnf,AttTrnf,Backspace,Target",
     "BTOnOff,Cancel,BlindTrnf,AttTrnf,Backspace,Target"),
    ("inConference", "Ajout à une conférence", "BTOnOff,Cancel,Dial,Backspace,Target", "BTOnOff,Cancel,Dial,Backspace,Target"),
]


def key_catalog(model_name: str | None) -> dict | None:
    """Ce que l'ecran de modeles de provisionnement offre pour un modele ; None si le modele n'a pas de disposition
    connue (seuls les GXP21xx du gabarit 1.0.11.106 pour l'instant)."""
    layout = GS_VPK_LAYOUT.get((model_name or "").upper())
    if not layout:
        return None
    fixed, total = layout
    return {
        "fixed": fixed, "total": total, "per_page": VPK_KEYS_PER_PAGE, "pages": -(-total // VPK_KEYS_PER_PAGE),
        "modes": [{"key": k, "label": l, "fixed_only": k in FIXED_ONLY_MODES} for k, l in GS_KEY_MODE_LABELS],
        "softkeys": {
            "idle_count": SOFTKEY_IDLE_COUNT, "call_count": SOFTKEY_CALL_COUNT,
            "idle_modes": [{"key": k, "label": l} for k, l in SOFTKEY_IDLE_MODES],
            "call_modes": [{"key": k, "label": l} for k, l in SOFTKEY_CALL_MODES],
            "idle_system": SOFTKEY_IDLE_SYSTEM,
            "states": [{"key": k, "label": l, "options": o.split(","), "default": d.split(",")} for k, l, o, d in SOFTKEY_STATES],
        },
    }


def softkey_items(softkeys: dict | None) -> list[tuple[str, str]]:
    """Elements « alias » a envoyer pour les boutons sous l'ecran d'un modele de provisionnement. Tout est envoye
    (non defini = valeur par defaut du gabarit), pour que le telephone ne garde pas d'anciens reglages."""
    sk = softkeys or {}
    out: list[tuple[str, str]] = []
    idle = sk.get("idle") or []
    for i in range(SOFTKEY_IDLE_COUNT):
        k = idle[i] if i < len(idle) else {}
        out += [(f"pks.softkey.{i + 1}.keyMode", k.get("mode") or "Default"),
                (f"pks.softkey.{i + 1}.account", str(k.get("account") or 0)),
                (f"pks.softkey.{i + 1}.description", k.get("description") or ""),
                (f"pks.softkey.{i + 1}.value", k.get("value") or "")]
    call = sk.get("call") or []
    for i in range(SOFTKEY_CALL_COUNT):
        k = call[i] if i < len(call) else {}
        out += [(f"pks.scSoftkey.{i + 1}.mode", k.get("mode") or "Default"),
                (f"pks.scSoftkey.{i + 1}.description", k.get("description") or ""),
                (f"pks.scSoftkey.{i + 1}.value", k.get("value") or "")]
    out.append(("softkeys.state.idle.hideSystemKeys", ",".join(sk.get("hide_idle") or [])))
    layouts = sk.get("layouts") or {}
    custom = any(layouts.get(k) and layouts[k] != d.split(",") for k, _, _, d in SOFTKEY_STATES)
    out.append(("softkeys.layout.enable", "Yes" if custom else "No"))
    for k, _, _, d in SOFTKEY_STATES:
        out.append((f"softkeys.layout.state.{k}", ",".join(layouts.get(k) or d.split(","))))
    return out
