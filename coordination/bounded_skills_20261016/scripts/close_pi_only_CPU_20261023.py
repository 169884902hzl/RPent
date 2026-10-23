"""Summarize registered native whole-task policy rollouts, retaining attempts."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path


def reference(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def wilson(k, n):
    if not n: return None
    z = 1.959963984540054; d = 1+z*z/n
    c = (k/n+z*z/(2*n))/d; h = z*math.sqrt(k*(n-k)/n**3+z*z/(4*n*n))/d
    return [max(0., c-h), min(1., c+h)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    root = Path('/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/execution_repairs_20261022/option_ceiling_20261022')
    previous = {r['case']: r for r in map(json.loads,
        (root/'measured_anchor_2db20013/CPU_closed40/comparison.jsonl').read_text().splitlines())}
    output = args.run/'CPU_pi_only46'; output.mkdir(exist_ok=False)
    rows = []
    for shard in range(4):
        plan = json.loads((args.run/f'preparation/pi_only_shard{shard}.json').read_text())
        for index, job in enumerate(plan['jobs']):
            pointer = json.loads((args.run/f'pi_only_shard{shard}/closed_{index:03d}.json').read_text())
            summary = Path(pointer['path']); assert reference(summary) == pointer
            row = json.loads(summary.read_text())
            assert row['arm_id'] == job['arm_id'] and row['initial_snapshot'] == job['initial_snapshot']
            assert all(row[k] == 0 for k in ('oracle_choices_used', 'private_goal_queries_used',
                'decision_model_calls', 'own_skill_calls', 'SAM_calls'))
            assert row['sim_steps'] > 0 and row['vla_inference_calls'] > 0
            attempts_path = Path(row['attempt_records']['path'])
            assert reference(attempts_path) == row['attempt_records']
            attempts = [json.loads(s) for s in attempts_path.read_text().splitlines()]
            assert 1 <= len(attempts) <= 2 and len(attempts) == row['attempts']
            assert attempts[0]['initial_physics_sha256'] == row['initial_physics_sha256']
            if len(attempts) == 2:
                assert attempts[1]['initial_physics_sha256'] == attempts[0]['final_physics_sha256']
            compact = {k: row[k] for k in ('arm_id', 'case', 'domain', 'success', 'sim_steps',
                'wall_s', 'attempts', 'initial_physics_sha256', 'initial_snapshot', 'policy_seed')}
            compact.update(raw=pointer, attempt_records=row['attempt_records'],
                first_attempt_success=attempts[0]['native_success'],
                stops=[a['stop_reason'] for a in attempts])
            if row['domain'] == 'd2':
                old = previous[row['case']['name']]
                old_digest = old['first_replay_initial_physics_sha256']
                compact.update(oracle_replay_success=old['success'],
                    sampled_success=old['sampled_envelope_success'], model_success=old['model_success'],
                    A1_M_success=old['A1_M_success'],
                    same_complete_initial_as_oracle=(old_digest == row['initial_physics_sha256']) if old_digest else None)
            rows.append(compact)
    assert len(rows) == len({r['arm_id'] for r in rows}) == 46
    groups = {}
    for domain in ('d2', 'original'):
        group = [r for r in rows if r['domain'] == domain]; k = sum(r['success'] for r in group)
        groups[domain] = {'success': k, 'n': len(group), 'wilson95': wilson(k, len(group)),
            'first_attempt_success': sum(r['first_attempt_success'] for r in group),
            'retried': sum(r['attempts'] == 2 for r in group),
            'retry_success': sum(r['success'] and not r['first_attempt_success'] for r in group)}
    by_suite = {}
    for suite in sorted({r['case']['episode']['suite'] for r in rows if r['domain'] == 'd2'}):
        group = [r for r in rows if r['case']['episode']['suite'] == suite]
        k = sum(r['success'] for r in group)
        by_suite[suite] = {'success': k, 'n': len(group), 'wilson95': wilson(k, len(group))}
    data = output/'episodes.jsonl'
    data.write_text(''.join(json.dumps(r, sort_keys=True)+'\n' for r in rows))
    report = {'groups': groups, 'D2_by_suite': by_suite,
        'D2_initial_matches': dict(Counter(str(r['same_complete_initial_as_oracle']) for r in rows if r['domain'] == 'd2')),
        'episodes': reference(data), 'parent_comparison': reference(root/'measured_anchor_2db20013/CPU_closed40/comparison.jsonl'),
        'source_commit': plan['source_commit'], 'entry_sha256': plan['entry_sha256'],
        'training': False, 'evaluation_only': True,
        'scope': 'native whole task; one same-world retry, original6 are three init identities at two inherited K labels'}
    (output/'manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    table = ['| 局 | π仅整句 | 首次 | 重试次数 | 当前oracle回放 | 采样包络 | 模型 | A1-M |', '|---|---:|---:|---:|---:|---:|---:|---:|']
    for row in sorted(rows, key=lambda r:r['arm_id']):
        values = [int(row['success']), int(row['first_attempt_success']), row['attempts']-1]
        values += [('?' if row.get(key) is None else int(row[key])) for key in
            ('oracle_replay_success', 'sampled_success', 'model_success', 'A1_M_success')]
        table.append('| '+row['arm_id']+' | '+' | '.join(map(str, values))+' |')
    (output/'paired_table.md').write_text('\n'.join(table)+'\n')
    print(json.dumps(report))


if __name__ == '__main__': main()
