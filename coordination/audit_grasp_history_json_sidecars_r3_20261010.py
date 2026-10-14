"""Enumerate raw JSON in every retained historical directory, without scoring."""

from collections import Counter
import datetime
import hashlib
import json
import os
from pathlib import Path

from coordination.audit_grasp_history_remaining_files_r8 import FORBIDDEN, PRUNE
from coordination.audit_grasp_history_json_sidecars_r2_20261010 import RAW_NAMES

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
INDEX = ROOT / 'coordination/grasp_truth_registered_v3_history_20261010_r6'
PRIOR = ROOT / 'coordination/grasp_history_json_sidecars_20261010_r2/review.json'
OUT = ROOT / 'coordination/grasp_history_json_sidecars_20261010_r3'


def main():
    old = json.loads(PRIOR.read_text())
    if old['errors']:
        raise ValueError('resolve parent JSON capture errors first')
    roots = json.loads((INDEX / 'parent_root_inventory.json').read_text())
    records = list(old['records'])
    known = {item['path'] for item in records}
    families, exclusions, errors, reviewed = Counter(), [], [], []
    OUT.mkdir(exist_ok=False)
    (OUT / 'inputs').mkdir()
    for number, root in enumerate(roots, 1):
        top = Path(root['path'])
        if FORBIDDEN.search(top.name):
            exclusions.append({'path': str(top), 'reason': 'prohibited_PRO_MAX_sealed_human102'})
            continue
        queue = [top]
        while queue:
            directory = queue.pop()
            if FORBIDDEN.search(str(directory)):
                exclusions.append({'path': str(directory), 'reason': 'prohibited_PRO_MAX_sealed_human102'})
                continue
            try:
                children = list(os.scandir(directory))
            except OSError as exc:
                errors.append({'path': str(directory), 'error': repr(exc)})
                continue
            reviewed.append(str(directory))
            for child in children:
                if child.is_dir(follow_symlinks=False):
                    if (child.name not in PRUNE and not child.name.startswith(('source_', 'step_'))
                            and not child.name.endswith(('.png', '.npz', '.jpg', '.jpeg', '.mp4'))):
                        queue.append(Path(child.path))
                elif child.is_file(follow_symlinks=False) and child.name.endswith('.json'):
                    families[child.name] += 1
                    if child.name not in RAW_NAMES or child.path in known:
                        continue
                    try:
                        data = Path(child.path).read_bytes()
                        value = json.loads(data)
                    except (OSError, ValueError) as exc:
                        errors.append({'path': child.path, 'error': repr(exc)})
                        continue
                    sha = hashlib.sha256(data).hexdigest()
                    captured = OUT / 'inputs' / (sha + '.json')
                    if not captured.exists():
                        captured.write_bytes(data)
                    records.append({'path': child.path, 'captured_path': str(captured), 'sha256': sha,
                        'bytes': len(data), 'fields': list(value) if isinstance(value, dict) else [],
                        'source_format': 'json', 'new_labels_not_computed': True})
                    known.add(child.path)
        if number % 20 == 0:
            print(json.dumps({'roots': number, 'total_roots': len(roots),
                'directories': len(reviewed), 'raw_JSON_records': len(records)}), flush=True)
    report = {'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'parent_review': str(PRIOR), 'parent_review_sha256': hashlib.sha256(PRIOR.read_bytes()).hexdigest(),
        'scope_root_inventory': str(INDEX / 'parent_root_inventory.json'),
        'scope_root_inventory_sha256': hashlib.sha256((INDEX / 'parent_root_inventory.json').read_bytes()).hexdigest(),
        'roots': len(roots), 'directories': len(reviewed), 'records': records, 'errors': errors,
        'exclusions': exclusions, 'raw_names': sorted(RAW_NAMES), 'pruned_payload_directories': sorted(PRUNE),
        'filename_counts': dict(Counter(Path(r['path']).name for r in records)),
        'all_JSON_filename_counts_for_review': dict(families),
        'scope': 'all non-payload directories under the pinned historical root inventory; prohibited inputs excluded',
        'new_labels_not_computed': True, 'exhaustive_claim': False}
    (OUT / 'visited_directories.json').write_text(json.dumps(reviewed, indent=2) + '\n')
    (OUT / 'review.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('records','exclusions')}, indent=2), flush=True)


if __name__ == '__main__':
    main()
