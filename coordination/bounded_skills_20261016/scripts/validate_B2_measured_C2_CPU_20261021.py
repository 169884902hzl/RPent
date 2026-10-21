"""Validate a measured B2 release with C2's published CPU consumer."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys


def ref(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def wilson(k, n):
    if not n:
        return None
    z = 1.959963984540054
    d = 1+z*z/n
    c = (k/n+z*z/(2*n))/d
    w = z*math.sqrt(k*(n-k)/n**3+z*z/(4*n*n))/d
    return [c-w, c+w]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--consumer', type=Path, required=True)
    p.add_argument('--schema', type=Path, required=True)
    p.add_argument('--package', type=Path, required=True)
    a = p.parse_args()
    sys.path.insert(0, str(a.consumer.resolve(strict=True)))
    from robot_decider.bounded_choice.skill_package import SkillPackageBridge
    from robot_decider.bounded_choice.measured_labels import build_measured_label
    import robot_decider.bounded_choice.measured_labels as module

    bridge = SkillPackageBridge(a.schema)
    manifest = json.loads((a.package/'manifest.json').read_bytes())
    data = Path(manifest['data']['path'])
    assert ref(data) == manifest['data']
    rows, groups, coverage = [], defaultdict(list), []
    for line in data.read_bytes().splitlines():
        row = json.loads(line)
        bridge.validate_request(row['public_request'])
        label = build_measured_label(bridge, row['public_request'], row['prefix'], row)
        rows.append({'record_id': row['record_id'], **label})
        if label['coverage_issues']:
            coverage.append({'record_id': row['record_id'], 'issues': label['coverage_issues']})
        candidates = {c['id']: c for c in row['public_request']['candidates']}
        for branch in row['branches']:
            candidate = candidates[branch['candidate_id']]
            params = candidate['parameters']
            variant = ('self' if branch['method_family'] != 'vla' else 'full_task'
                if params.get('mode') == 'task' else params.get('preparation', 'default'))
            groups[(row['case']['category'], variant)].extend(branch['trials'])
    stats = []
    for (category, variant), trials in sorted(groups.items()):
        known = [t for t in trials if type(t['success']) is bool]
        k, n = sum(t['success'] for t in known), len(known)
        stats.append({'category': category, 'variant': variant, 'trials': len(trials),
            'known': n, 'success': k, 'wilson95_over_trials': wilson(k, n),
            'unknown': len(trials)-n, 'zero_step_trials': sum(not t['sim_steps'] for t in trials)})
    result = {'consumer': ref(Path(module.__file__)), 'source_contract_identity': bridge.identity,
        'data': ref(data), 'positions': len(rows), 'rows': rows,
        'coverage_issues': coverage, 'GPU_used': False, 'training_executed': False}
    (a.package/'C2_intake_validation.json').write_text(json.dumps(result, indent=2)+'\n')
    (a.package/'metrics.json').write_text(json.dumps({'positions': len(rows), 'groups': stats,
        'scope': 'measured subtask branches; Wilson over trials with repeated states, not class-generalization intervals'}, indent=2)+'\n')
    print(json.dumps({'positions': len(rows), 'statuses': [r['status'] for r in rows],
        'coverage_issues': coverage, 'groups': stats}))


if __name__ == '__main__':
    main()
