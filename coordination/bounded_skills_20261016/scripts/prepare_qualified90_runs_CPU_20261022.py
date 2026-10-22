"""Register repeated original90 forks after the complete strict N1 result."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys


def ref(path):
    path = path.resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'parent', 'qualification', 'smoke-parent', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--commit', required=True)
    p.add_argument('--parent-sha256', required=True)
    a = p.parse_args()
    assert ref(a.parent)['sha256'] == a.parent_sha256
    q = json.loads(a.qualification.read_bytes())
    assert q['closed'] == 30 and not q['missing'] and q['all_complete_initial_hashes_match']
    assert q['before']['success'] == 25 and q['after']['success'] >= 24
    plan = copy.deepcopy(json.loads(a.parent.read_bytes()))
    assert len(plan['cases']) == 90 and not plan['training'] and not plan['confirmation']
    for case in plan['cases']:
        d = case['diagnostic']
        assert d['domain'] == 'original' and d['self_repeats'] == 2
        assert [v['name'] for v in d['vla_variants']] == ['initial_pose']
    plan['source_commit'] = a.commit
    plan['qualified_N1'] = ref(a.qualification)
    plan['repeat_registration']['qualified_parent'] = ref(a.parent)
    sys.path.insert(0, str(a.source.resolve(strict=True)))
    from scripts.probe_bounded_hybrid_repair import validate_plan
    from scripts.bounded_state_exclusions import check_exclusions
    validate_plan(plan)
    exclusions = check_exclusions(plan['cases'], plan['permanent_exclusions'])
    a.output.mkdir(parents=True, exist_ok=False)
    manifest = a.output/'manifest.json'
    manifest.write_text(json.dumps(plan, indent=2)+'\n')
    smoke = json.loads(a.smoke_parent.read_bytes())
    assert len(smoke['jobs']) == 10 and all(row['kind'] == 'smoke' for row in smoke['jobs'])
    smoke.update(source=str(a.source), source_commit=a.commit, qualified_N1=ref(a.qualification))
    (a.output/'smoke10.json').write_text(json.dumps(smoke, indent=2)+'\n')
    batch = {'domain': 'original', 'source': str(a.source), 'source_commit': a.commit,
        'manifest': ref(manifest)}
    common = {'training': False, 'confirmation': False, 'sam3_entry': smoke['sam_entry']}
    startup = {**common, 'selected_n': 1, 'batches': [{**batch, 'indices': [0]}]}
    # Separate immutable case groups. Only completed states become resumable
    # checkpoints; no partially executed fork is treated as a closed label.
    groups = [list(range(start, min(start+30, 90))) for start in range(0, 90, 30)]
    actual = {**common, 'selected_n': 8,
        'batches': [{**batch, 'indices': group} for group in groups]}
    (a.output/'startup_plan.json').write_text(json.dumps(startup, indent=2)+'\n')
    (a.output/'batch_plan.json').write_text(json.dumps(actual, indent=2)+'\n')
    metadata = {'commit': a.commit, 'qualified_execution_tree':
        '9d00ee63ab2196b95f8374e8245d9dea2ed8782b', 'training': False}
    with (a.source/'SOURCE_REVISION.json').open('x') as stream:
        json.dump(metadata, stream, indent=2)
    registration = {'manifest': ref(manifest), 'qualified_N1': ref(a.qualification),
        'states': 90, 'self_trials': 180, 'initial_pose_trials': 270,
        'source_tree': a.commit, 'execution_stack_matches_qualified_N1': True,
        'permanent_exclusions': exclusions, 'physical_rollouts': 0, 'training': False}
    (a.output/'registration.json').write_text(json.dumps(registration, indent=2)+'\n')
    print(json.dumps(registration))


if __name__ == '__main__':
    main()
