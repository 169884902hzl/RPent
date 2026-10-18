# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Compare a real saved prefix state with labels and a nonoracle prefix."""
# ruff: noqa: E402 -- immutable source and CPU selected before imports
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
parser = argparse.ArgumentParser()
parser.add_argument('--job', default='9046_120')
parser.add_argument('--row', type=int, default=0)
args = parser.parse_args()
root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
prep = json.loads((base/'reports/chunk_v3_offline_labels_20261018_preparation.json').read_text())
sys.path.insert(0, prep['snapshot'])

from robots.libero.bounded_offline_labels import annotate_prefix, load_annotation_state
from rpent.skill_package.contract import legal_after

directory, = (root/'results/bounded_skills/feasibility_20261017'/('job'+args.job)).glob('*_oracle_k4')
choices = directory/'choices.jsonl'
labels_path = directory/'private_oracle_labels.jsonl'
row = json.loads(choices.read_bytes().splitlines()[args.row])
expected = json.loads(labels_path.read_bytes().splitlines()[args.row])
ref = row['private_prefix_annotation_state']
state = load_annotation_state(ref['path'], ref['sha256'])
assert not hasattr(state['adapter'].p.env, 'step')
request = row['request']
records = []
for position in expected['positions']:
    started = time.perf_counter()
    actual = annotate_prefix(state, request, position['prefix'])
    elapsed = time.perf_counter()-started
    mismatches = [field for field in ('legal', 'rule_acceptable', 'selected')
                  if actual[field] != position[field]]
    records.append({'kind': 'oracle_path', 'elapsed_s': elapsed, 'mismatches': mismatches, 'label': actual})
    assert not mismatches, (position['prefix'], mismatches)
first = expected['positions'][0]['selected']
alternative = next(c for c in request['candidates'] if c['id'] != first
    and c['id'] in legal_after(request, []) and c['skill'] == 'nudge')
started = time.perf_counter()
actual = annotate_prefix(state, request, [alternative['id']])
records.append({'kind': 'nonoracle_prefix', 'prefix_candidate': alternative,
    'elapsed_s': time.perf_counter()-started, 'label': actual})
assert actual['legal'] == list(legal_after(request, [alternative['id']]))
assert set(actual['rule_acceptable']) <= set(actual['legal'])
report = {'job': args.job, 'row': args.row, 'source_commit': prep['source_commit'], 'snapshot': prep['snapshot'],
    'state_reference': ref, 'snapshot_bytes': Path(ref['path']).stat().st_size,
    'inputs': [{'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
               for path in (choices, labels_path)], 'records': records,
    'oracle_positions': len(expected['positions']), 'oracle_mismatches': 0,
    'physics_steps': 0, 'gpu_used': False, 'training': False,
    'scope': 'actual captured measured state; private conditional rule labels, no branch outcome claim',
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
suffix = f'_row{args.row}' if args.row else ''
output = base/'reports'/f'offline_prefix_{args.job}{suffix}_CPU_20261018.json'
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'output': str(output), 'snapshot_bytes': report['snapshot_bytes'],
    'oracle_positions': report['oracle_positions'], 'oracle_mismatches': 0,
    'results': [{'kind': r['kind'], 'elapsed_s': r['elapsed_s'], 'status': r['label']['status'],
                 'legal_n': len(r['label']['legal']), 'acceptable_n': len(r['label']['rule_acceptable'])}
                for r in records]}))
