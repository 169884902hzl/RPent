"""Extract measured execution evidence without treating terminal buckets as causes."""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASE = ROOT / 'coordination/bounded_skills_20261016'
SOURCE = BASE / 'reports/original20_support_interim_r18_20261019.json'


def compact(value):
    """Keep scalar diagnostics and receipt checks, omit full clouds and traces."""
    if isinstance(value, dict):
        return {key: compact(item) for key, item in value.items()
                if key not in {'trace', 'trajectory', 'points', 'cloud', 'waypoints',
                               'stationary_scene', 'target_world_points', 'scene_world_points'}}
    if isinstance(value, list):
        if len(value) > 24:
            return {'items': len(value), 'first': compact(value[:2]), 'last': compact(value[-2:])}
        return [compact(item) for item in value]
    return value


def main():
    cohort = json.loads(SOURCE.read_bytes())
    records = []
    failed_receipts = Counter()
    for episode in cohort['cohort']['rows']:
        if episode['success']:
            continue
        choices, = Path(episode['record']).parent.glob('*oracle_k4/choices.jsonl')
        rows = []
        digest = hashlib.sha256()
        with choices.open('rb') as stream:
            for line in stream:
                digest.update(line)
                rows.append(json.loads(line))
        samples = []
        counts = Counter()
        for row in rows:
            request = row['request']
            receipts = row.get('receipts', [])
            for receipt in receipts:
                if receipt['outcome'] != 'success':
                    key = (receipt['skill'], receipt['outcome'], receipt['stop_reason'])
                    counts[key] += 1
                    failed_receipts[key] += 1
            samples.append({
                'index': row.get('index'), 'event': row.get('event'),
                'sim_steps_before': row.get('sim_steps_before'),
                'sim_steps_after': row.get('sim_steps_after'),
                'request_robot': request.get('robot'), 'anchors': request['anchors'],
                'candidate_count': len(request['candidates']),
                'candidate_skill_counts': dict(Counter(c['skill'] for c in request['candidates'])),
                'private_pre_execution_snapshot': row.get('private_pre_execution_snapshot'),
                'private_prefix_annotation_state': row.get('private_prefix_annotation_state'),
                'receipts': receipts,
                'execution_details': compact(row.get('execution_details', [])),
                'candidate_screen_diagnostics': compact(row.get('candidate_screen_diagnostics', [])),
                'chunk_execution': compact(row.get('chunk_execution')),
            })
        records.append({
            'case': episode['case'], 'category': episode['report_category'],
            'recorded_terminal_bucket': episode['failure_phase'],
            'terminal_diagnostic': episode.get('terminal_diagnostic'),
            'sim_steps': episode['sim_steps'], 'skill_sim_steps': episode['skill_sim_steps'],
            'choices': str(choices), 'choices_sha256': digest.hexdigest(),
            'request_rows': len(rows),
            'failure_receipts': [{'skill': k[0], 'outcome': k[1], 'stop_reason': k[2], 'n': n}
                                 for k, n in sorted(counts.items())],
            'samples': samples,
        })
    report = {
        'source_commit': cohort['source_commit'], 'scope': 'saved development logs only',
        'cohort': {'path': str(SOURCE), 'sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest()},
        'completed_physical': cohort['completed_physical'], 'failures': len(records),
        'category_counts': dict(Counter(row['category'] for row in records)),
        'failed_receipts': [{'skill': k[0], 'outcome': k[1], 'stop_reason': k[2], 'n': n}
                            for k, n in sorted(failed_receipts.items())],
        'records': records, 'physics_steps': 0, 'rpc_calls': 0, 'gpu_used': False,
        'training': False, 'confirmation': False,
        'interpretation': 'Terminal buckets and receipt success are not task/root-cause labels; inspect measured geometry and execution details.',
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    output = BASE / 'reports/original_failures_stage_audit_CPU_20261019.json'
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: report[k] for k in ('failures', 'category_counts', 'failed_receipts')}))


if __name__ == '__main__':
    main()
