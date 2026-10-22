"""Keep the registered original90 states; add the requested repeat counts."""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--commit', required=True)
    p.add_argument('--parent', type=Path, required=True)
    p.add_argument('--parent-sha256', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    raw = a.parent.read_bytes()
    if hashlib.sha256(raw).hexdigest() != a.parent_sha256:
        raise ValueError('registered original90 manifest changed')
    sys.path.insert(0, str(a.source.resolve(strict=True)))
    from scripts.bounded_state_exclusions import check_exclusions
    from scripts.probe_bounded_hybrid_repair import validate_plan

    plan = copy.deepcopy(json.loads(raw))
    counts = Counter(case['category'] for case in plan['cases'])
    if len(plan['cases']) != 90 or len(counts) != 9 or set(counts.values()) != {10}:
        raise ValueError('the exact original90 cohort must contain ten states per category')
    if plan['training'] or plan['confirmation']:
        raise ValueError('expected the original development fork registration')
    for case in plan['cases']:
        diagnostic = case['diagnostic']
        if diagnostic['domain'] != 'original' or not case['source_training_parent_ids']:
            raise ValueError('only registered original train positions are eligible')
        diagnostic['include_self'] = True
        diagnostic['self_repeats'] = 2
        diagnostic['vla_variants'] = [variant for variant in diagnostic['vla_variants']
            if variant['name'] == 'initial_pose']
        if len(diagnostic['vla_variants']) != 1:
            raise ValueError('initial-pose variant was not in the original registration')
    plan['source_commit'] = a.commit
    plan['repeat_registration'] = {
        'parent': {'path': str(a.parent), 'sha256': a.parent_sha256},
        'same_registered_states_and_trial_seeds': True,
        'self_trials_per_state': 2, 'initial_pose_trials_per_state': 3,
        'other_old_variants_not_rescored': True, 'requires_N1_and_physical_startup': True,
    }
    validate_plan(plan)
    exclusion = check_exclusions(plan['cases'], plan['permanent_exclusions'])
    a.output.mkdir(parents=True, exist_ok=False)
    path = a.output/'manifest.json'
    path.write_text(json.dumps(plan, indent=2)+'\n')
    summary = {'manifest': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'states': 90, 'categories': dict(counts), 'self_trials': 180, 'initial_pose_trials': 270,
        'physical_rollouts': 0, 'permanent_exclusions': exclusion, 'training': False}
    (a.output/'registration.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
