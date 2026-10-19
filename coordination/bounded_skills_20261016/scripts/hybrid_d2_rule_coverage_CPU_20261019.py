"""List coverage of unchanged rules on exactly the registered D2 forty cases."""
import hashlib
import json
import os
import platform
import sys
from collections import Counter
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', LIBERO_TYPE='pro', OPENBLAS_NUM_THREADS='1')
ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
SOURCE = ROOT / 'source_bounded_hybrid_d2_startup_20261019_2a869b26'
sys.path.insert(0, str(SOURCE))

from robots.libero.bounded_hybrid_diagnostic import split_subtasks, validate_d2_episode
from libero.libero.envs.bddl_utils import robosuite_parse_problem


def main():
    manifest = ROOT / 'results/bounded_skills/hybrid_d2_20261019/preparation/D2_hybrid_manifest_2a869b26.json'
    plan = json.loads(manifest.read_bytes())
    assert len(plan['cases']) == 40 and not plan['training'] and not plan['confirmation']
    records = []
    for case in plan['cases']:
        validate_d2_episode(case['episode'])
        path = Path(case['bddl']['path'])
        assert hashlib.sha256(path.read_bytes()).hexdigest() == case['bddl']['sha256']
        goals = robosuite_parse_problem(str(path))['goal_state']
        subtasks, unsupported = split_subtasks(goals)
        records.append({'case': case, 'private_goals': goals, 'subtasks': subtasks,
                        'unsupported': unsupported, 'status': 'uncovered' if unsupported else 'covered'})
    covered = [row for row in records if not row['unsupported']]
    report = {'manifest': {'path': str(manifest), 'sha256': hashlib.sha256(manifest.read_bytes()).hexdigest()},
              'source_snapshot': str(SOURCE), 'host': platform.node(), 'interpreter': sys.executable,
              'registered_cases': 40, 'covered_cases': len(covered), 'uncovered_cases': 40-len(covered),
              'subtask_modes_in_covered_cases': dict(Counter(task['mode'] for row in covered for task in row['subtasks'])),
              'records': records, 'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False,
              'training': False, 'history_updates': False, 'private_labels_model_visible': False,
              'limitations': ['Static rule coverage is not binding, candidate availability, physical feasibility or success.',
                              'No PRO-specific progress rule is created; no paths outside the pinned manifest are read.'],
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    output = ROOT / 'coordination/bounded_skills_20261016/reports/hybrid_d2_rule_coverage_CPU_20261019.json'
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({key: report[key] for key in ('registered_cases', 'covered_cases', 'uncovered_cases',
                                                 'subtask_modes_in_covered_cases')}))


if __name__ == '__main__':
    main()
