#!/usr/bin/env python3
"""Ajoute UN fait a la file d'attente locale Graphiti (SIPV -> ERPCRM).

SIPV n'a pas d'acces direct au conteneur graphiti-mcp (vit sur la VM ERPCRM,
voir .claude/skills/graphiti-knowledge/SKILL.md) -- ce script se contente
d'ajouter une ligne JSON a scripts/graphiti_queue.jsonl (local, append-only,
jamais commite). Un cron (push_graphiti_queue.py, a la minute) pousse
ensuite ce fichier vers ERPCRM par scp, ou le consommateur de file cote
ERPCRM (graphiti_queue_consumer.py) le traite comme n'importe quel autre
incoming/*.jsonl.

Lit un objet JSON sur stdin, format triplet (fait precis entre 2 entites
nommees deja verifiees par Claude -- pas d'extraction LLM, voir TASK-040.9) :
{"type": "triplet", "source": "NomExact", "edge_name": "RELATES_TO",
 "fact": "...(le pourquoi, reference TASK-SXXX integree)...", "target": "NomExact",
 "source_summary": "..." (seulement si source nouvelle),
 "target_summary": "..." (seulement si target nouvelle)}

Usage : python3 scripts/graphiti_queue_fact.py <<< '{"type": "triplet", ...}'
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

QUEUE_FILE = Path(__file__).resolve().parent / 'graphiti_queue.jsonl'


def main() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        print('JSON vide sur stdin', file=sys.stderr)
        return 2
    try:
        item = json.loads(raw)
    except Exception as exc:
        print(f'JSON invalide : {exc}', file=sys.stderr)
        return 2

    if item.get('type') == 'triplet':
        for field in ('source', 'edge_name', 'fact', 'target'):
            if not item.get(field):
                print(f'Champ manquant pour un triplet : {field}', file=sys.stderr)
                return 2
    elif 'episode_body' not in item:
        print('Format non reconnu -- attendu "type": "triplet" ou un episode avec episode_body', file=sys.stderr)
        return 2

    item.setdefault('reference_time', datetime.now(timezone.utc).isoformat())

    with QUEUE_FILE.open('a', encoding='utf-8') as f:
        f.write(json.dumps(item, ensure_ascii=False) + '\n')

    print(f'OK -- ajoute a {QUEUE_FILE}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
