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
# Comptes qu'une touche peut viser (« Account. 0 - Account 1, ... » de chaque section du gabarit)
GS_ACCOUNTS = {"GXP2130": 3, "GXP2140": 4, "GXP2160": 6, "GXP2135": 4, "GXP2170": 6}
VPK_KEYS_PER_PAGE = 8
SPARE_LINE_ACCOUNT = 1      # « Account 2 » (0 = compte 1) : jamais configure par SIPV, sert aux touches Ligne suivantes

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
    first_line = False
    for n in range(1, total + 1):
        b = by_index.get(n)
        mode = GS_KEY_MODES.get(b.button_type, -1) if b else -1
        if n > fixed and mode != -1:
            mode = mode - 10 if mode >= 10 else -1          # Ligne / Ligne partagee impossibles sur une touche dynamique
        account = (b.sip_account_index - 1) if b and mode != -1 else 0
        label = (b.label or "") if b and mode != -1 else ""
        # Regle (Philippe, 2026-10-14, prouvee sur le 102 d'apres son GXP2170 de l'UCM) : en Line Mode (P8369=1), la
        # 1re touche Ligne du compte 1 garde son nom ; les suivantes pointent vers le compte 2, jamais configure par SIPV,
        # sans description -> rien d'affiche, et elles servent aux appels suivants du compte 1. (Un texte vide ou
        # invisible ne suffit pas : le telephone le remplace par l'Account Name, puis par l'identifiant SIP.)
        if b and b.button_type == "line" and account == 0 and mode == 0:
            if first_line:
                account, label = SPARE_LINE_ACCOUNT, ""
            first_line = True
        pm, pa, pd, pv = vpk_pcodes(n)
        out.append({"n": n, "p_mode": pm, "p_account": pa, "p_label": pd, "p_value": pv, "mode": mode,
                    "account": account, "label": label,
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


# Boutons sous l'ecran (softkeys) : disposition par etat d'appel (« Custom Softkey Layout »), en P-codes du gabarit
# officiel (section « Settings/Programmable Keys / Softkeys Settings » : P2923 active la disposition, puis un P-code par
# etat ; les options sont la liste « String: » de chaque etat). Philippe (2026-10-14) : seulement les options des softkeys.
# (P-code, libelle, options possibles du gabarit, preference Simple IP = config de Philippe sur ses telephones)
SOFTKEY_ENABLE_PCODE = 2923
SOFTKEY_STATES = [
    (2925, "En composition",
     "BTPhonebook,BTOnOff,SpkOnOff,EndCall,ReConf,ConfRoom,Redial,Dial,Backspace,PickUp,Target,ShowHideLabel,Custom1,Custom2,Custom3",
     "EndCall,Redial,Dial,Backspace,Target"),
    (2935, "Composition sans décrocher",
     "BTPhonebook,DirectIP,Onhook,Cancel,Dial,Backspace,Target,ShowHideLabel,Custom1,Custom2,Custom3",
     "Cancel,Dial,Backspace,Onhook,Target"),
    (2926, "Ça sonne", "Answer,Reject,Forward,ReConf,ShowHideLabel,Custom-Silence,Custom1,Custom2,Custom3", "Reject,Answer,Forward"),
    (2927, "Appel en cours de composition",
     "BTOnOff,SpkOnOff,Cancel,EndCall,ReConf,ConfRoom,ConfCall,ShowHideLabel,Custom1,Custom2,Custom3", "EndCall"),
    (2928, "En appel",
     "BTPhonebook,BTOnOff,SpkOnOff,EndCall,ReConf,ConfRoom,ConfCall,Cancel,NewCall,Swap,Transfer,Trnf>VM,DialDTMF,BSCCenter,"
     "URecord,Record,UCallPark,PrivateHold,CallPark,ShowHideLabel,Custom-Hold,Custom-Conference,Custom-Mute,Custom1,Custom2,Custom3",
     "EndCall,NewCall,Transfer,Cancel,Swap,Record"),
    (2933, "En conférence",
     "BTOnOff,SpkOnOff,EndCall,Kick,NewCall,Trnf>VM,DialDTMF,BSCCenter,URecord,Record,ConfRoom,Add,ShowHideLabel,Custom-Hold,"
     "Custom-Split,Custom-Mute,Custom1,Custom2,Custom3",
     "EndCall,NewCall,Record"),
    (2929, "En garde", "ReConf,Resume,HoldTrnf,ConfCall,Add,ShowHideLabel,Custom-NewCall,Custom-EndCall,Custom1,Custom2,Custom3",
     "Custom-EndCall,Custom-NewCall,Resume,Add"),
    (2930, "Appel échoué", "SpkOnOff,EndCall,ReConf,ConfRoom,ShowHideLabel,Custom-NewCall,Custom1,Custom2,Custom3",
     "EndCall,Custom-NewCall"),
    (2931, "En transfert", "BTOnOff,SpkOnOff,Cancel,BlindTrnf,AttTrnf,Backspace,Target,ShowHideLabel,Custom1,Custom2,Custom3",
     "Cancel,BlindTrnf,AttTrnf,Backspace,Target"),
    (2932, "Ajout à une conférence", "BTOnOff,SpkOnOff,Cancel,Dial,Backspace,Target,ShowHideLabel,Custom1,Custom2,Custom3",
     "Cancel,Dial,Backspace,Target"),
]
# Anciennes cles (noms « alias » du 2026-10-14 matin) -> P-code : les dispositions deja enregistrees restent valables
SOFTKEY_ALIAS = {"inDialing": 2925, "inOnhookDialing": 2935, "InRinging": 2926, "inCalling": 2927, "inCallConnected": 2928,
                 "inConferenceConnected": 2933, "inOnhold": 2929, "inCallFailed": 2930, "inTransfer": 2931, "inConference": 2932}
# Libelles affiches (comme la page web du telephone) ; les autres s'affichent tels quels
SOFTKEY_LABELS = {"BTPhonebook": "Phonebook (BT)", "BTOnOff": "BT On/Off", "SpkOnOff": "Spk On/Off"}


def key_catalog(model_name: str | None) -> dict | None:
    """Ce que l'ecran de modeles de provisionnement offre pour un modele ; None si le modele n'a pas de disposition
    connue (seuls les GXP21xx du gabarit 1.0.11.106 pour l'instant)."""
    layout = GS_VPK_LAYOUT.get((model_name or "").upper())
    if not layout:
        return None
    fixed, total = layout
    return {
        "fixed": fixed, "total": total, "per_page": VPK_KEYS_PER_PAGE, "pages": -(-total // VPK_KEYS_PER_PAGE),
        "accounts": GS_ACCOUNTS.get((model_name or "").upper(), 1),
        "modes": [{"key": k, "label": l, "fixed_only": k in FIXED_ONLY_MODES} for k, l in GS_KEY_MODE_LABELS],
        "softkeys": {
            "labels": SOFTKEY_LABELS,
            "states": [{"key": f"P{k}", "label": l, "options": o.split(","), "default": d.split(",")} for k, l, o, d in SOFTKEY_STATES],
        },
    }


def _layout_key(k: str) -> str:
    return f"P{SOFTKEY_ALIAS[k]}" if k in SOFTKEY_ALIAS else k


def normalize_layouts(layouts: dict | None) -> dict:
    """Dispositions par etat, cles = « P2925 »... (accepte les anciennes cles « alias »)."""
    return {_layout_key(k): v for k, v in (layouts or {}).items()}


def softkey_items(softkeys: dict | None) -> list[tuple[int, str]]:
    """P-codes des boutons sous l'ecran : disposition activee (P2923=1) et la liste de chaque etat (non definie =
    preference Simple IP). Tout est envoye pour que le telephone ne garde pas d'anciens reglages."""
    layouts = normalize_layouts((softkeys or {}).get("layouts"))
    out: list[tuple[int, str]] = [(SOFTKEY_ENABLE_PCODE, "1")]
    for k, _, _, d in SOFTKEY_STATES:
        out.append((k, ",".join(layouts.get(f"P{k}") or d.split(","))))
    return out
