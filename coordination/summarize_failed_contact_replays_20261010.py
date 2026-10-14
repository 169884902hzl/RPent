"""Contact-phase diagnosis of trace replays; never substitute historical labels."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import shutil

from coordination.classify_grasp_contact_phases_20261010 import diagnose


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('paired_summary', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows_path = args.paired_summary / 'rows.jsonl'
    cache, records = {}, []
    for index in map(json.loads, rows_path.open()):
        path = Path(index['input'])
        if path not in cache:
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != index['input_sha256']:
                raise ValueError('closed physical evidence changed')
            cache[path] = data.splitlines()
        raw = json.loads(cache[path][index['line'] - 1])
        category = index['group'].rsplit('/', 1)[-1].removesuffix('_analytic')
        outcome = ('success' if index['registered_v3'] is True else
                   'failure' if index['registered_v3'] is False else 'unknown')
        item = {'case': index['case'], 'category': category, 'method': 'analytic_trace_replay',
                'state_sha256': index['state_sha256'], 'physical_outcome': outcome}
        record = diagnose(raw, item)
        record.pop('historical_physical_outcome', None)
        record.update(replay_v3_outcome=outcome, baseline_exclusive_v2=index['baseline_exclusive_v2'],
                      object_category=raw['case']['object_category'],
                      baseline_failure_reason=index['baseline_failure_reason'],
                      baseline_case=index['baseline_case'], input=pin(path), line=index['line'])
        records.append(record)
    groups = defaultdict(list)
    for row in records:
        groups[row['category']].append(row)
    args.output.mkdir(parents=True, exist_ok=False)
    source_snapshots = []
    for source in (Path(__file__), Path(__file__).with_name('classify_grasp_contact_phases_20261010.py')):
        copied = args.output / source.name
        shutil.copyfile(source, copied)
        source_snapshots.append(pin(copied))
    records_path = args.output / 'records.jsonl'
    records_path.write_text(''.join(json.dumps(r) + '\n' for r in records))
    summary = {'paired_rows': pin(rows_path), 'records': pin(records_path),
               'producer': pin(Path(__file__)),
               'source_snapshots': source_snapshots,
               'diagnostic_dependency': pin(Path(__file__).with_name('classify_grasp_contact_phases_20261010.py')),
               'groups': {name: {'n': len(rows),
                   'new_v3_outcomes': dict(Counter(r['replay_v3_outcome'] for r in rows)),
                   'classes': dict(Counter(r['contact_failure_class'] for r in rows)),
                   'phase_samples_saved': sum(r['saved_phase_samples'] > 0 for r in rows)}
                   for name, rows in groups.items()},
               'limits': ['Replays are a subset selected by old failures, not a method success-rate sample.',
                          'Contact phase diagnosis never fills missing historical registered-v3 truth.',
                          'Private contact evidence is used only in this analysis, never in control.'],
               'training_allowed': False, 'qualification_allowed': False}
    (args.output / 'manifest.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
