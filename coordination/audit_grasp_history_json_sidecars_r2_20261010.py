"""Pin additional raw grasp diagnostic JSON beside the enumerated ledgers."""

from collections import Counter
import datetime
import hashlib
import json
import os
from pathlib import Path

from coordination.audit_grasp_history_remaining_files_r8 import FORBIDDEN

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT = ROOT / 'coordination/grasp_truth_registered_v3_history_20261010_r6'
CENSUS = ROOT / 'coordination/grasp_history_remaining_files_r8_20261010/review.json'
PRIOR = ROOT / 'coordination/grasp_history_json_sidecars_20261010_r1/review.json'
OUT = ROOT / 'coordination/grasp_history_json_sidecars_20261010_r2'
RAW_NAMES = {'private_grasp_diagnostic.json', 'private_skill_diagnostic.json',
             'private_grasp.json', 'grasp_truth.json', 'private_diagnostics.json',
             'episode.json', 'episodes.json', 'trial.json'}


def main():
    previous = json.loads(PRIOR.read_text())
    files = json.loads((PARENT / 'input_files.json').read_text())
    census = json.loads(CENSUS.read_text())
    paths = [item['path'] for item in files] + [item['path'] for item in census['unindexed_jsonl']]
    directories = {Path(path).parent for path in paths}
    directories.update(Path(item['path']) for item in json.loads((PARENT / 'parent_root_inventory.json').read_text()))
    records = list(previous['records'])
    known = {record['path'] for record in records}
    errors, dispositions = [], []
    OUT.mkdir(exist_ok=False)
    (OUT / 'inputs').mkdir()
    for number, directory in enumerate(sorted(directories), 1):
        if FORBIDDEN.search(str(directory)):
            continue
        try:
            children = list(os.scandir(directory))
        except OSError as exc:
            errors.append({'path': str(directory), 'error': repr(exc)})
            continue
        for child in children:
            if child.name not in RAW_NAMES or child.path in known or not child.is_file(follow_symlinks=False):
                continue
            path = Path(child.path)
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
            record = {'path': str(path), 'captured_path': str(captured), 'sha256': sha,
                      'bytes': len(data), 'fields': list(value) if isinstance(value, dict) else [],
                      'source_format': 'json', 'new_labels_not_computed': True}
            records.append(record)
            known.add(str(path))
            dispositions.append({'path': str(path), 'sha256': sha,
                                 'root_type': type(value).__name__, 'fields': record['fields']})
        if number % 1000 == 0:
            print(json.dumps({'directories': number, 'total': len(directories),
                              'raw_json_sidecars': len(records)}), flush=True)
    report = {'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'scope': previous['scope'], 'directories': len(directories),
              'records': records, 'errors': errors,
              'filename_counts': dict(Counter(Path(record['path']).name for record in records)),
              'additional_dispositions': dispositions,
              'parent_review': {'path': str(PRIOR), 'sha256': hashlib.sha256(PRIOR.read_bytes()).hexdigest()},
              'new_labels_not_computed': True, 'exhaustive_claim': False,
              'census_sha256': hashlib.sha256(CENSUS.read_bytes()).hexdigest()}
    (OUT / 'review.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: value for key, value in report.items()
                      if key not in ('records', 'additional_dispositions')}), flush=True)


if __name__ == '__main__':
    main()
