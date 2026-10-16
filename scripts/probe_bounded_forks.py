"""Record private same-snapshot self/VLA pick branches; never training input.

The task/actuator/RNG snapshot is created once and passed directly to both
branches. Public requests are remeasured independently after restoration.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import pickle

from scripts.bounded_state_exclusions import check_exclusions
from scripts.probe_bounded_feasibility import ORIGINAL_SUITES, episode, services
from scripts.probe_bounded_motion import original_session, write
from scripts.v5_probe_preflight import pinned_file, validate_registered_states


def run_pair(case, endpoints, output, config, *, session=original_session, run=episode):
    """Preserve the same private full state and separate all branch outputs."""
    output.mkdir(parents=True, exist_ok=False)
    ep = case['episode']
    facade, _ = session(ep['suite'], ep['task'], ep['seed'], 10000)
    try:
        snapshot = facade.snapshot()
    finally:
        facade.close()
    raw = pickle.dumps(snapshot, protocol=5)
    path = output/'private_initial_snapshot.pkl'
    path.write_bytes(raw)
    identity = {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(),
                'contains': 'physics_actuators_controllers_environment_rng_and_wrapper_counters',
                'model_visible': False, 'origin': 'original_development_initial_state'}
    rows = []
    for arm in ('oracle_k4', 'call_vla'):
        result = run(case, arm, endpoints, output/arm, config,
                     initial_snapshot=snapshot, pick_branch=True)
        rows.append({'branch': arm, 'snapshot': identity, 'result': result})
        write(output/f'{arm}_branch_result.json', rows[-1])
    report = {'case': case, 'snapshot': identity, 'branches': rows,
              'source_commit': os.environ.get('SOURCE_COMMIT'), 'training': False,
              'training_admission': False,
              'scope': 'same-initial-snapshot pick subtask; task-success stays separate',
              'private_label': 'simulation_grasp_truth_v3_after_branch'}
    write(output/'pair.json', report)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--count', type=int, default=1)
    args = parser.parse_args()
    if os.environ.get('LIBERO_TYPE') != 'standard' or args.count < 1:
        parser.error('LIBERO_TYPE=standard and count>=1 required')
    plan = json.loads(args.manifest.resolve(strict=True).read_text())
    if not plan.get('permanent_exclusions'):
        raise ValueError('same-state forks require a pinned permanent-state registry')
    cases = [case for case in plan['cases'] if case['category'] in
             {'bowl_transfer', 'box_transfer', 'cup_transfer', 'container'}][:args.count]
    if not cases or any(case['episode']['suite'] not in ORIGINAL_SUITES for case in cases):
        raise ValueError('original object-transfer development cases required')
    for case in cases:
        pinned_file(case['bddl'], 'original_task_bddl')
    validate_registered_states(cases)
    exclusion = check_exclusions(cases, plan['permanent_exclusions'])
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    write(output/'state_exclusion_check.json', exclusion)
    with services(output, vla=True) as endpoints:
        for case in cases:
            run_pair(case, endpoints, output/case['name'], plan.get('budget', {}))


if __name__ == '__main__':
    main()
