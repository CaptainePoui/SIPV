"""Transforme un gabarit officiel Grandstream (P-codes) en catalogue d'options pour l'ecran des modeles de provisionnement
(TASK-051, 2026-10-14). Seule source : le fichier du fabricant (~/GrandStream/Template_Config_Pcode). Rien n'est invente :
libelle = 1re ligne de commentaire, choix = « 0 - No, 1 - Yes » du commentaire, defaut = « Default is X » sinon la valeur
du gabarit. Les touches (VPK) et les boutons sous l'ecran ont leurs propres editeurs et sont exclus.

Usage : python3 parse_gs_template.py <gabarit.txt> <sortie.json>
"""
import json
import re
import sys

SECTION = re.compile(r"^#+\s*((?:Account \d+|Network|Maintenance|Phonebook|Settings|Programmable Keys)\s*/\s*[^#.]+?)\s*#*\s*$")
PLINE = re.compile(r"^(#\s*)?P(\d+)\s*=\s*(.*?)\s*$")
CHOICE = re.compile(r"(?:^|[,.;:]\s*)(-?\d+|[a-z]{2,4}(?:[-_][a-z]{2})?)\s+-\s+([A-Za-z][^;]*?)(?=\s*(?:,\s*(?:-?\d+|[a-z]{2,4}(?:[-_][a-z]{2})?)\s+-|;|\.\s|\.$|$))")
TABLE = re.compile(r"^(.+?)(?:\t+|\s{3,})(\S+)$")
META = ("mandatory", "string", "number")
# Deja geres par leurs propres editeurs (touches, boutons sous l'ecran, fond d'ecran) ou hors sujet pour l'instant
EXCLUDE = ("Programmable Keys/Virtual Multi-Purpose Keys", "Programmable Keys/Softkeys Settings", "Extension Boards/EXT Setting",
           "Programmable Keys/Physical Multi-Purpose Keys", "Programmable Keys/Idle Screen Settings",
           "Programmable Keys/Call Screen Settings", "Extension Boards/EXT Setting/EXT MPK")
EXCLUDE_P = {"P2916", "P2917"}   # fond d'ecran : son propre editeur


def clean_path(p: str) -> list[str]:
    parts = [x.strip() for x in re.split(r"\s*/\s*", p) if x.strip()]
    if parts and parts[0] == "Programmable Keys":
        parts = ["Settings"] + parts
    return parts


def parse(text: str) -> dict:
    lines = text.replace("\r", "").split("\n")
    sections: dict[tuple, dict] = {}
    path: list[str] = []
    group = None
    comments: list[str] = []
    blocks: list[list[str]] = []
    last_label = None
    seen: set[str] = set()
    for i, raw in enumerate(lines):
        line = raw.strip()
        m = SECTION.match(line)
        if m and not PLINE.match(line):
            path, group, comments = clean_path(m.group(1)), None, []
            continue
        if re.match(r"^#{5,}\s*$", line):
            # sous-groupe : « ####\n# DHCP\n#### »
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            after = lines[i + 2].strip() if i + 2 < len(lines) else ""
            if nxt.startswith("#") and not nxt.startswith("##") and re.match(r"^#{5,}", after) and "/" not in nxt:
                group = nxt.lstrip("# ").rstrip("# ").strip() or None
            comments = []
            continue
        pm = PLINE.match(line)
        if pm and path:
            pcode, value = "P" + pm.group(2), pm.group(3)
            full = "/".join((path[1:] if path[0] == "Settings" else path) + ([group] if group else []))
            if any(full == e or full.startswith(e + "/") for e in EXCLUDE) or pcode in seen or pcode in EXCLUDE_P:
                comments = []
                continue
            seen.add(pcode)
            text_c = [c for c in comments if c]
            raw_c = list(text_c)
            k = len(blocks) - 1
            while k >= 0 and (not text_c or text_c[0].lower().startswith(META) or "P Value" in text_c[0]):
                text_c = [c for c in blocks[k] if c] + text_c
                raw_c = text_c
                k -= 1
            if text_c and text_c[0].lower().startswith(META) and last_label:
                text_c = [f"{last_label} (suite)"] + text_c       # ex. adresse IP : un P-code par chiffre
            if not text_c:
                comments = []
                continue
            first = text_c[0]
            if not first.endswith("(suite)"):
                last_label = re.split(r"\.\s", first)[0]
            label = re.split(r"\.\s+(?=-?\d+\s*-|Default|Number|Max|Valid|The |If |Range)", first)[0].strip().rstrip(".")
            label = re.sub(r"\s*\((?:in )?(?:seconds?|minutes?|ms|milliseconds?)\)\s*$", lambda x: x.group(0), label)
            blob = " ".join(text_c)
            choices = []
            for c in raw_c or text_c:
                tm = TABLE.match(c.replace("\t", "\t"))
                if tm and len(text_c) > 4 and not re.search(r"\d+\s*-\s*[A-Za-z]", c):
                    choices.append({"value": tm.group(2), "label": tm.group(1).strip()})
            for c in text_c:
                if re.search(r"(?:-?\d+|[a-z]{2})\s+-\s+[A-Za-z]", c) and not c.lower().startswith("number:"):
                    for v, l in CHOICE.findall(c):
                        l = l.strip().rstrip(".")
                        if l and not l.lower().startswith("default") and len(l) < 60:
                            choices.append({"value": v, "label": l})
            # dedoublonner en gardant l'ordre
            uniq, cv = [], set()
            for c in choices:
                if c["value"] not in cv:
                    cv.add(c["value"]); uniq.append(c)
            default = value
            for c in text_c:
                dm = re.search(r"Default (?:is|value is)\s*:?\s*\"?([^\".,;]+?)\"?\s*(?:\.|,|;|\(|$)", c)
                if dm:
                    default = dm.group(1).strip(); break
            rng = re.search(r"Number:\s*(-?\d+)\s*(?:-|to|--)\s*(-?\d+)", blob)
            kind = "select" if len(uniq) >= 2 else ("number" if re.search(r"Number", blob) else "string")
            key = tuple(path + ([group] if group else []))
            sec = sections.setdefault(key, {"path": list(key), "options": []})
            sec["options"].append({
                "p": pcode, "label": label, "type": kind, "choices": uniq if kind == "select" else [],
                "default": default, "min": int(rng.group(1)) if rng else None, "max": int(rng.group(2)) if rng else None,
                "help": [c for c in text_c[1:] if not c.lower().startswith(("mandatory", "string", "number:"))][:4],
                "optional": bool(pm.group(1)),
            })
            comments, blocks = [], []
            continue
        if line.startswith("#"):
            comments.append(line.lstrip("#").strip())
        elif not line:
            if comments:
                blocks = (blocks + [comments])[-3:]
            comments = []
    out = [s for s in sections.values() if s["options"]]
    return {"source": None, "sections": out}


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    data = parse(open(src, encoding="utf-8", errors="replace").read())
    data["source"] = src.rsplit("/", 1)[-1]
    json.dump(data, open(dst, "w"), ensure_ascii=False, indent=1)
    n = sum(len(s["options"]) for s in data["sections"])
    print(f"{len(data['sections'])} sections, {n} options -> {dst}")
