"""Replay saved public stove measurements only; never rewrite physical labels."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from robots.libero.v5_stove_measurement import measured_stove_endpoint

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
MANIFEST = ROOT / 'results/harness_v5/fixture540_measured_handle_selection/preparation_runtime547_smoke30/fixtures_measured_handle_selection.json'
EXPECTED_MANIFEST_SHA = '0b92f748b70d93d714fdf8a8fbf724a10e79da5c59462c3d29ab84019e123269'
JOB = ROOT / 'results/harness_v5/fixture540_measured_handle_selection/source547_smoke30/job4150'
DEST = ROOT / 'results/harness_v5/runtime542_readonly_audit_CPU_20261006/job4150_stove_overwrite_CPU.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


assert sha(MANIFEST) == EXPECTED_MANIFEST_SHA
plan = json.loads(MANIFEST.read_text())
registered = {c['name']: c for c in plan['cases']}
records = []
for part in range(6):
    ledger = JOB / f'part{part}' / 'episodes.jsonl'
    if not ledger.exists():
        continue
    for line, raw in enumerate(ledger.read_text().splitlines(), 1):
        row = json.loads(raw)
        case = row['case']
        if case['type'] != 'stove_turn_on':
            continue
        assert registered[case['name']] == case
        episode = Path(row['output_dir'])
        assert episode.is_relative_to(JOB)
        trace = episode / 'private_skill_diagnostic.json'
        data = json.loads(trace.read_text())
        first = data['first_attempt']
        stove = first['verification_measurements']['stove_rgbd']
        # Only the public RGB-D samples enter this recomputation. Private
        # success labels and joint coordinates are not loaded into it.
        verified, evidence = measured_stove_endpoint(stove['before'], stove['after'], case['mode'],
            second_after=stove['second_after'], interval_s=stove['measurement_interval_s'])
        receipt = first['receipt']
        records.append({'case': case['name'], 'trace_path': str(trace), 'trace_sha256': sha(trace),
            'ledger': str(ledger), 'ledger_sha256': sha(ledger), 'line': line,
            'actual_saved_receipt': {key: receipt.get(key) for key in
                ('verification', 'articulate_verified', 'reason', 'chunks', 'effect')},
            'saved_public_endpoint': stove['endpoint'], 'CPU_recomputed_endpoint': verified,
            'CPU_recomputed_reason': evidence['reason'],
            'before': {key: stove['before'].get(key) for key in ('source_step', 'state', 'features')},
            'after': {key: stove['after'].get(key) for key in ('source_step', 'state', 'features')}})
report = {'scope': 'SOURCE547 public RGB-D endpoint receipts only; no model or physics replay; '
                   'all original private/public labels unchanged',
    'manifest': str(MANIFEST), 'manifest_sha256': EXPECTED_MANIFEST_SHA,
    'records': records, 'root_cause': 'The generic legacy measured_articulation branch executes '
        'after verify_stove when endpoint_before is None, overwriting the typed stove result.',
    'minimal_fix': 'elif self.articulate_verification_v1 and stove_before is None; '
        'RGB-D thresholds and True/False/None semantics are unchanged.'}
DEST.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'report': str(DEST), 'sha256': sha(DEST), 'cases': len(records),
                  'CPU_results': [r['CPU_recomputed_endpoint'] for r in records]}))
