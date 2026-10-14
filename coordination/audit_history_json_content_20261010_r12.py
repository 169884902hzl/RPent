"""Inspect every JSON sidecar in the pinned historical directory census.

Record content hashes and unindexed grasp evidence without computing labels.
The directory list is fixed; live runs outside it are not historical inputs.
"""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import datetime
import hashlib
import json
from pathlib import Path
import re


SIGNAL = re.compile(rb'"(?:private_grasp_phase|private_setup_hold|contact_samples|sustained_hold|'
                    rb'private_hold_truth_v[23]|private_true_sustained_grasp|true_sustained_grasp|'
                    rb'true_sustained_grasp_during_skill|finger_contact|dual_finger_contact|relative_com_tcp|lower_extent_m)"\s*:')
EVIDENCE_KEYS = {'private_grasp_phase', 'private_setup_hold', 'contact_samples', 'sustained_hold',
                 'private_hold_truth_v2', 'private_hold_truth_v3', 'private_true_sustained_grasp',
                 'true_sustained_grasp', 'true_sustained_grasp_during_skill'}


def objects(value, pointer=''):
    if isinstance(value, dict):
        if EVIDENCE_KEYS.intersection(value) or (
                isinstance(value.get('samples'), list)
                and any(isinstance(s, dict) and ('finger_contact' in s or 'dual_finger_contact' in s or 'relative_com_tcp' in s
                             or ('lower_extent_m' in s and 'sim_time' in s))
                        for s in value['samples'])):
            yield pointer, sorted(EVIDENCE_KEYS.intersection(value)), list(value)
            # A container can repeat its first_attempt. Preserve that explicit
            # alias for review; it is not another independent physical run.
        for key, child in value.items():
            if key in ('samples', 'checks'):
                continue
            escaped = str(key).replace('~', '~0').replace('/', '~1')
            yield from objects(child, pointer + '/' + escaped)
    elif isinstance(value, list):
        for number, child in enumerate(value):
            yield from objects(child, pointer + '/' + str(number))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--census', type=Path, required=True)
    parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    census = json.loads((args.census / 'review.json').read_text())
    if census['errors']:
        raise ValueError('directory census has unresolved errors')
    directories = json.loads((args.census / 'visited_directories.json').read_text())
    pinned = {r['path']: r for r in json.loads((args.index / 'input_files.json').read_text())}
    indexed_sidecars = {r['path'] for r in json.loads(
        (args.index / 'JSON_sidecar_dispositions.json').read_text())}
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'inputs').mkdir()
    counts, families, dispositions, errors = Counter(), Counter(), Counter(), []

    def inspect(directory):
        records = []
        for path in sorted(Path(directory).glob('*.json')):
            if not path.is_file() or path.is_symlink():
                continue
            try:
                item = pinned.get(str(path))
                data = Path(item['captured_path']).read_bytes() if item else path.read_bytes()
                if item and hashlib.sha256(data).hexdigest() != item['sha256']:
                    raise ValueError('pinned historical JSON changed')
                digest = hashlib.sha256(data).hexdigest()
                record = {'path': str(path), 'sha256': digest, 'bytes': len(data),
                          'already_pinned': bool(item), 'previous_sidecar_disposition': str(path) in indexed_sidecars}
                if not SIGNAL.search(data):
                    record['disposition'] = 'no_grasp_evidence_field'
                else:
                    value = json.loads(data)
                    found = list(objects(value))
                    record['disposition'] = 'unindexed_grasp_object' if found else 'no_grasp_container'
                    record['objects'] = [{'pointer': p, 'evidence_keys': k, 'fields': f}
                                         for p, k, f in found]
                    if found:
                        captured = Path(item['captured_path']) if item else args.output / 'inputs' / (digest + '.json')
                        if not captured.exists():
                            captured.write_bytes(data)
                        record['captured_path'] = str(captured)
                records.append(record)
            except (OSError, ValueError) as exc:
                records.append({'path': str(path), 'disposition': 'error', 'error': repr(exc)})
        return records

    with (args.output / 'file_dispositions.jsonl').open('x') as ledger, \
            (args.output / 'unindexed_objects.jsonl').open('x') as candidates, \
            ThreadPoolExecutor(max_workers=4) as pool:
        for number, batch in enumerate(pool.map(inspect, directories), 1):
            for record in batch:
                ledger.write(json.dumps(record, sort_keys=True) + '\n')
                families[Path(record['path']).name] += 1
                dispositions[record['disposition']] += 1
                if record['disposition'] == 'unindexed_grasp_object':
                    candidates.write(json.dumps(record, sort_keys=True) + '\n')
                if record['disposition'] == 'error':
                    errors.append(record)
            if number % 2000 == 0:
                ledger.flush()
                candidates.flush()
                print(json.dumps({'directories': number, 'total': len(directories),
                                  'files': sum(dispositions.values()), 'dispositions': dispositions}), flush=True)
    report = {'generated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'directory_census': str(args.census),
              'directory_list_sha256': hashlib.sha256((args.census / 'visited_directories.json').read_bytes()).hexdigest(),
              'index_manifest_sha256': hashlib.sha256((args.index / 'index_manifest.json').read_bytes()).hexdigest(),
              'directories': len(directories), 'files': sum(dispositions.values()),
              'dispositions': dict(dispositions), 'filename_counts': dict(families), 'errors': errors,
              'census_filename_counts_match': dict(families) == census['all_JSON_filename_counts_for_review'],
              'producer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'new_labels_computed': False, 'exhaustive_claim': False,
              'known_JSON_files_reinspected_for_nested_windows': True,
              'legacy_finger_contact_only_windows_included': True}
    (args.output / 'review.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'filename_counts'}, indent=2))


if __name__ == '__main__':
    main()
