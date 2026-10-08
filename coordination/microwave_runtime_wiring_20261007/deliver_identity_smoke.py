"""Pin completed smoke outputs, then attach private post-hoc endpoint labels."""

import argparse
import hashlib
import json
from pathlib import Path


def ref(path):
    return {'path': str(path.resolve(strict=True)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--preparation', type=Path, required=True)
    parser.add_argument('--run-output', type=Path, required=True)
    parser.add_argument('--job', type=int, required=True)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--snapshot-preparation', type=Path)
    args = parser.parse_args()
    prep, run = args.preparation, args.run_output
    summary = prep / f'public_summary{args.job}.json'
    public = json.loads(summary.read_text())
    if public['private_labels_read'] is not False:
        raise ValueError('public analysis must finish before attaching private diagnostics')
    row = json.loads((run / 'episodes.jsonl').read_text())
    private_path = prep / f'private_diagnostic{args.job}.json'
    private_path.write_text(json.dumps({'public_summary_precedes_private_pairing': ref(summary),
        'private_before': row['first_attempt']['private_before'],
        'private_after': row['first_attempt']['private_after'],
        'native_original_success_latched': row.get('native_original_success_latched'),
        'use': 'post-hoc diagnostic only; never runtime/verification/training'}, indent=2) + '\n')
    snapshot_prep = args.snapshot_preparation or prep
    manifest = args.manifest or prep / 'capture_identity40.json'
    paths = [prep / 'preparation.json', snapshot_prep / 'source_identity.json',
             manifest, prep / 'launcher_CPU_preflight.log',
             snapshot_prep / 'snapshot_import.json', prep / f'startup{args.job}_observed.json',
             summary, private_path, run / 'episodes.jsonl', run / 'physical_startup_contract.json']
    identity = json.loads((snapshot_prep / 'source_identity.json').read_text())
    result = {'job': args.job, 'cohort': 'visited-original-state development smoke',
        'qualification': False, 'train_allowed': False, 'new_training_rows': 0,
        'source_snapshot': {'path': identity['path'], 'commit': identity['commit'], 'archive': identity['archive']},
        'files': [ref(path) for path in paths],
        'summary_producer': ref(Path(__file__).with_name('summarize_identity_runtime.py')),
        'delivery_producer': ref(Path(__file__))}
    output = prep / f'delivery_manifest{args.job}.json'
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(ref(output)))
