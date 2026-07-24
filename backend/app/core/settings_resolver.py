def resolve_setting(field_name: str, *levels):
    """
    Mecanisme d'heritage de reglages, du plus specifique au plus general.

    Chaine standard du projet : poste (SIPExtension) -> profil de poste
    (ExtensionProfile) -> compagnie (Tenant) -> global (singleton settings).
    Chaque niveau est un objet ORM (ou None si absent, ex: pas de profil assigne) ;
    une colonne nullable a None signifie "herite du niveau parent". Le premier
    niveau qui porte une valeur non-None pour field_name gagne.

    Usage : resolve_setting("max_message_length", extension, profile, tenant, global_settings)
    """
    for level in levels:
        if level is None:
            continue
        value = getattr(level, field_name, None)
        if value is not None:
            return value
    return None
