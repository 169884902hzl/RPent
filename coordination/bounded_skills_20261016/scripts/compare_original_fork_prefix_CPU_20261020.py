# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Compare actual original-fork policy traffic and captured physical starts."""

import argparse
import json
import pickle
import sys
from pathlib import Path


def lines(path):
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--left', type=Path, required=True)
    parser.add_argument('--right', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source.resolve(strict=True)))
    import numpy as np

    from robots.libero.bounded_hybrid_diagnostic import snapshot_digest

    rows, unavailable = [], []
    for right_assignment in sorted(args.right.glob('N*/*/assignment.json')):
        right_owner = json.loads(right_assignment.read_bytes())
        name = right_owner['case']['name']
        left_assignment = next(args.left.glob('N*/*_'+name+'/assignment.json'), None)
        if left_assignment is None:
            unavailable.append({'case': name, 'reason': 'left_worker_absent'})
            continue
        left_owner = json.loads(left_assignment.read_bytes())
        assert left_owner['case']['episode'] == right_owner['case']['episode']
        for trial in ('call_vla_1', 'call_vla_2', 'call_vla_3'):
            left = left_assignment.parent/name/trial
            right = right_assignment.parent/name/trial
            a, b = left/'vla_inputs.jsonl', right/'vla_inputs.jsonl'
            if not a.exists() or not b.exists():
                unavailable.append({'case': name, 'trial': trial, 'reason': 'one_or_both_ledgers_not_yet_available'})
                continue
            inputs = lines(a), lines(b)
            predictions = lines(a.with_name('vla_predictions.jsonl')), lines(b.with_name('vla_predictions.jsonl'))
            common = min(map(len, inputs))
            action_common = min(map(len, predictions))
            initial = [pickle.loads((folder.parent/'private_branchpoint.pkl').read_bytes())['physics']
                for folder in (left, right)]
            hashes = [snapshot_digest(value) for value in initial]
            mismatch = next((i for i in range(common) if inputs[0][i] != inputs[1][i]), None)
            action_mismatch = next((i for i in range(action_common)
                if predictions[0][i] != predictions[1][i]), None)
            changed = sorted(k for k in inputs[0][mismatch]['fields'].keys() |
                inputs[1][mismatch]['fields'].keys()
                if inputs[0][mismatch]['fields'].get(k) != inputs[1][mismatch]['fields'].get(k)) if mismatch is not None else []
            rows.append({'case': name, 'trial': trial, 'left_inputs': str(a), 'right_inputs': str(b),
                'sampling_seed': inputs[0][0]['sampling_seed'],
                'same_sampling_seed': inputs[0][0]['sampling_seed'] == inputs[1][0]['sampling_seed'],
                'initial_physics_sha256': hashes, 'same_captured_physics': hashes[0] == hashes[1],
                'initial_sim_state_max_error': float(np.max(np.abs(np.asarray(initial[0]['sim_state'])-
                    np.asarray(initial[1]['sim_state'])))),
                'common_inference_calls': common, 'common_prediction_calls': action_common,
                'first_input_mismatch': mismatch, 'changed_input_fields': changed,
                'first_action_mismatch': action_mismatch,
                'same_recorded_prefix': bool(common and action_common and mismatch is None and action_mismatch is None)})
    args.output.write_text(json.dumps({'rows': rows, 'unavailable': unavailable,
        'matching_prefixes': sum(r['same_recorded_prefix'] for r in rows),
        'physics_steps': 0, 'gpu_used': False, 'training': False,
        'scope': 'observed policy prefix only; unobserved calls and success outcomes are not inferred'}, indent=2))
    print(json.dumps({'pairs': len(rows), 'matching_prefixes': sum(r['same_recorded_prefix'] for r in rows),
        'first_mismatches': [{k:r[k] for k in ('case','trial','first_input_mismatch','changed_input_fields','first_action_mismatch')}
            for r in rows if not r['same_recorded_prefix']]}))


if __name__ == '__main__':
    main()
