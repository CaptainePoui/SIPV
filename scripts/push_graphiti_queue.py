#!/usr/bin/env python3
"""Pousse la file d'attente locale Graphiti (scripts/graphiti_queue.jsonl)
vers ERPCRM par scp -- cote push uniquement (voir feedback_sipv_must_stay_autonomous,
jamais de pull depuis ERPCRM vers SIPV ni l'inverse pour le code/config).

Concu pour tourner via cron a la minute (idempotent : pousse le fichier
entier a chaque fois s'il a change depuis le dernier push -- suivi par
mtime/taille dans .graphiti_push_state.json local, jamais commite -- le
fichier local ne fait que grossir, un scp qui ecrase la copie distante avec
une version plus longue est sans risque, le consommateur cote ERPCRM
suit son propre offset de lecture sur ce fichier).

Destination : erpcrm:/home/simpleip/erpcrm/tools/knowledge/graphiti/incoming/sipv.jsonl
(alias SSH "erpcrm" defini dans ~/.ssh/config, cle dediee id_ed25519_erpcrm).
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
QUEUE_FILE = SCRIPT_DIR / 'graphiti_queue.jsonl'
STATE_FILE = SCRIPT_DIR / '.graphiti_push_state.json'
REMOTE = 'erpcrm:/home/simpleip/erpcrm/tools/knowledge/graphiti/incoming/sipv.jsonl'


def main() -> int:
    if not QUEUE_FILE.exists():
        return 0  # rien a pousser, pas d'erreur

    size = QUEUE_FILE.stat().st_size
    state = {}
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())
        except Exception:
            state = {}

    if state.get('last_pushed_size') == size:
        return 0  # rien de nouveau depuis le dernier push

    result = subprocess.run(
        ['scp', '-q', str(QUEUE_FILE), REMOTE],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        print(f'Echec push : {result.stderr.strip()}', file=sys.stderr)
        return 1

    STATE_FILE.write_text(json.dumps({'last_pushed_size': size}))
    print(f'Pousse ({size} octets) vers {REMOTE}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
