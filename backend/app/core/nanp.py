# Classification des numeros NANP (North American Numbering Plan) pour le plan
# d'appel (TASK-S018.5). Le NANP est partage entre le Canada, les USA et plusieurs
# pays des Caraibes -- il n'existe PAS de moyen de distinguer "Canada" de "USA" a
# partir du seul numero sans une table indicatif->pays, puisque les deux partagent
# le meme format a 10 chiffres. Liste ci-dessous = indicatifs regionaux assignes au
# Canada (verifiee contre la liste NANPA publique) -- a mettre a jour si de nouveaux
# indicatifs sont assignes (rare, quelques-uns par decennie).
CANADIAN_AREA_CODES = {
    "204", "226", "236", "249", "250", "289", "306", "343", "354", "365", "367",
    "368", "403", "416", "418", "431", "437", "438", "450", "468", "474", "506",
    "514", "519", "548", "579", "581", "584", "587", "604", "613", "639", "647",
    "672", "683", "705", "709", "742", "753", "778", "780", "782", "807", "819",
    "825", "867", "873", "902", "905",
}

TOLL_FREE_AREA_CODES = {"800", "833", "844", "855", "866", "877", "888"}
PREMIUM_AREA_CODE = "900"


def classify_number(digits: str) -> str:
    """
    Classe un numero compose (digits seulement, sans + ni espaces) en :
    'international' | 'premium' | 'toll_free' | 'canada' | 'us' | 'local'

    'local'  : moins de 10 chiffres (poste interne / court -- ne devrait pas
               atteindre cette fonction en pratique, le dialplan interne matche
               les postes avant les routes sortantes, mais gere proprement au cas ou).
    'us'     : NANP 10/11 chiffres, indicatif hors de CANADIAN_AREA_CODES --
               simplification documentee (regroupe aussi les quelques pays NANP
               des Caraibes sous "us" plutot que "canada", pas de 3e categorie
               demandee par l'utilisateur).
    """
    d = digits.lstrip("+")
    if d.startswith("011"):
        return "international"
    # Normalise 1NXXNXXXXXX -> NXXNXXXXXX
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    if len(d) != 10:
        if len(d) > 10:
            return "international"
        return "local"
    area_code = d[:3]
    if area_code == PREMIUM_AREA_CODE:
        return "premium"
    if area_code in TOLL_FREE_AREA_CODES:
        return "toll_free"
    if area_code in CANADIAN_AREA_CODES:
        return "canada"
    return "us"
