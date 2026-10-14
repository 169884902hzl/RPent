"""Inventory raw JSON sidecars beside the already enumerated history ledgers.

This records evidence and aliases, without computing grasp labels. Media and
simulator state payloads are not new trial records.
"""

from collections import Counter
import datetime
import hashlib
import json
from pathlib import Path

from coordination.audit_grasp_history_remaining_files_r8 import FORBIDDEN

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT = ROOT / 'coordination/grasp_truth_registered_v3_history_20261010_r6'
CENSUS = ROOT / 'coordination/grasp_history_remaining_files_r8_20261010/review.json'
OUT = ROOT / 'coordination/grasp_history_json_sidecars_20261010_r1'
RAW_NAMES = {'private_skill_diagnostic.json', 'private_grasp.json', 'grasp_truth.json',
             'private_diagnostics.json', 'episode.json', 'trial.json'}


def main():
    files = json.loads((PARENT / 'input_files.json').read_text())
    census = json.loads(CENSUS.read_text())
    paths = [item['path'] for item in files] + [item['path'] for item in census['unindexed_jsonl']]
    # The runner saves a sidecar in each attempted case directory. Include the
    # episode output roots too, including sidecars with no completed choices.
    directories = {Path(path).parent for path in paths}
    directories.update(Path(item['path']) for item in json.loads((PARENT / 'parent_root_inventory.json').read_text()))
    records, errors, other_names = [], [], Counter()
    OUT.mkdir(exist_ok=False)
    (OUT / 'inputs').mkdir()
    for number, directory in enumerate(sorted(directories), 1):
        if FORBIDDEN.search(str(directory)):
            continue
        try:
            children = list(directory.iterdir())
        except OSError as exc:
            errors.append({'path': str(directory), 'error': repr(exc)})
            continue
        for path in children:
            if path.name not in RAW_NAMES or not path.is_file():
                if path.suffix == '.json' and path.is_file():
                    other_names[path.name] += 1
                continue
            data = path.read_bytes()
            sha = hashlib.sha256(data).hexdigest()
            captured = OUT / 'inputs' / (sha + '.json')
            if not captured.exists():
                captured.write_bytes(data)
            try:
                value = json.loads(data)
            except ValueError as exc:
                errors.append({'path': str(path), 'sha256': sha, 'error': str(exc)})
                continue
            records.append({'path': str(path), 'captured_path': str(captured),
                            'sha256': sha, 'bytes': len(data),
                            'fields': list(value) if isinstance(value, dict) else [],
                            'new_labels_not_computed': True})
        if number % 1000 == 0:
            print(json.dumps({'directories': number, 'total': len(directories),
                              'raw_json_sidecars': len(records)}), flush=True)
    report = {'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'scope': 'raw trial JSON sidecars in enumerated ledger and episode-root directories',
              'directories': len(directories), 'records': records, 'errors': errors,
              'filename_counts': dict(Counter(Path(record['path']).name for record in records)),
              'other_json_filename_counts_for_review': dict(other_names),
              'new_labels_not_computed': True, 'exhaustive_claim': False,
              'census_sha256': hashlib.sha256(CENSUS.read_bytes()).hexdigest()}
    (OUT / 'review.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'records'}), flush=True)


if __name__ == '__main__':
    main()
