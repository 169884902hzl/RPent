"""Inspect filename families and excluded CPU trees before history recount."""

from collections import Counter
import datetime
import hashlib
import json
import os
from pathlib import Path
import re

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASE = ROOT / 'results/harness_v5'
INDEX = ROOT / 'coordination/grasp_truth_registered_v3_history_20261010_r6'
OUT = ROOT / 'coordination/grasp_history_remaining_files_r7_20261010'
FORBIDDEN = re.compile(r'(?i)(?:libero_(?:spatial|object|goal|10)_(?:task|swap)_t|(?:^|/)(?:A[1-4]|RULE)[-_]|sealed|liberomax|max160|human102)')
PRUNE = {'frames', 'images', 'videos', 'media', 'captures', 'state', 'states',
         'observation', 'observations', 'assets', 'preparation', 'preparation_r2',
         'source', '__pycache__', '.git', 'logs', 'empty_memory', 'perception'}


def scan():
    files = json.loads((INDEX / 'input_files.json').read_text())
    known = {item['path'] for item in files}
    roots = json.loads((INDEX / 'parent_root_inventory.json').read_text())
    families, candidates, exclusions, errors = Counter(), [], [], []
    directories = 0
    for number, entry in enumerate(roots, 1):
        top = Path(entry['path'])
        if FORBIDDEN.search(top.name):
            exclusions.append({'path': str(top), 'reason': 'PRO_MAX_sealed_or_human102'})
            continue
        queue = [top]
        while queue:
            directory = queue.pop()
            if FORBIDDEN.search(str(directory.relative_to(BASE))):
                exclusions.append({'path': str(directory), 'reason': 'PRO_MAX_sealed_or_human102'})
                continue
            try:
                entries = list(os.scandir(directory))
            except OSError as exc:
                errors.append({'path': str(directory), 'error': repr(exc)})
                continue
            directories += 1
            for child in entries:
                if child.is_dir(follow_symlinks=False):
                    if child.name not in PRUNE and not child.name.startswith(('source_', 'step_')):
                        queue.append(Path(child.path))
                elif child.is_file(follow_symlinks=False) and child.name.endswith('.jsonl'):
                    families[child.name] += 1
                    if child.path in known:
                        continue
                    try:
                        with open(child.path, 'rb') as stream:
                            first = stream.readline()
                        raw = json.loads(first) if first.strip() else None
                        keys = list(raw) if isinstance(raw, dict) else []
                        grasp_fields = sorted(set(keys) & {'first_attempt', 'first_receipt', 'receipt',
                            'private_grasp_phase', 'private_setup_hold', 'contact_samples',
                            'grasp_attempted', 'grasp_contact', 'dual_finger_contact'})
                        candidates.append({'path': child.path, 'root': str(top),
                            'first_row_fields': keys, 'grasp_fields': grasp_fields,
                            'first_row_sha256': hashlib.sha256(first).hexdigest(),
                            'full_ledger_not_captured_in_r6': True})
                    except (OSError, ValueError) as exc:
                        errors.append({'path': child.path, 'error': repr(exc)})
        if number % 50 == 0:
            print(json.dumps({'roots_processed': number, 'directories': directories,
                              'unindexed_jsonl': len(candidates)}), flush=True)
    report = {'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'index_manifest_sha256': hashlib.sha256((INDEX / 'index_manifest.json').read_bytes()).hexdigest(),
              'scope_root_inventory': str(INDEX / 'parent_root_inventory.json'),
              'roots': len(roots), 'directories': directories, 'filename_families': dict(families),
              'unindexed_jsonl': candidates, 'exclusions': exclusions, 'errors': errors,
              'new_labels_not_computed': True, 'exhaustive_claim': False}
    OUT.mkdir(exist_ok=False)
    (OUT / 'review.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'roots': len(roots), 'directories': directories,
                      'unindexed_jsonl': len(candidates), 'errors': len(errors)}, indent=2), flush=True)


if __name__ == '__main__':
    scan()
