"""Register independent complete-path replays from closed D2 branch records."""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def ref(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--parent-plan', type=Path, required=True)
    p.add_argument('--parent-results', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--allow-incomplete', action='store_true')
    a = p.parse_args()
    a.source = a.source.resolve(strict=True)
    sys.path.insert(0, str(a.source))
    from robots.libero.bounded_hybrid_paths import select_complete_path
    from robots.libero.bounded_hybrid_diagnostic import validate_d2_episode
    parent = json.loads(a.parent_plan.read_bytes())
    assert not parent['training'] and not parent['confirmation'] and len(parent['jobs']) == 40
    jobs, missing, selections = [], [], []
    for index, source_job in enumerate(parent['jobs']):
        assert source_job['kind'] == 'd2'
        validate_d2_episode(source_job['case']['episode'])
        pointer = a.parent_results/f'closed_{index:03d}.json'
        if not pointer.exists():
            missing.append(index)
            continue
        saved = json.loads(pointer.read_bytes())
        summary_path = Path(saved['summary'])
        assert saved['sha256'] == ref(summary_path)['sha256']
        summary = json.loads(summary_path.read_bytes())
        assert summary['case'] == source_job['case']
        assert summary['source_commit'] == parent['source_commit']
        assert summary.get('full_replay'), 'source must already contain a real independent replay'
        selection = select_complete_path(summary)
        assert ref(Path(source_job['manifest']['path'])) == source_job['manifest']
        original = json.loads(Path(source_job['manifest']['path']).read_bytes())
        job = {'kind': 'd2_replay', 'case': source_job['case'],
            'parent_case_index': index, 'parent_summary': ref(summary_path),
            'parent_initial': ref(summary_path.parent/'episode/private_initial.pkl'),
            'recovery_budget': source_job['recovery_budget'], 'path_selection': selection,
            'replay_seed_base': original['trial_seed_base']+1000000000+1000000*index}
        jobs.append(job)
        selections.append({'case': summary['case']['name'], 'selection': selection})
    if missing and not a.allow_incomplete:
        raise ValueError(f'parent branch batch has {len(missing)} unclosed cases')
    if not jobs:
        raise ValueError('no closed parent cases')
    revision = json.loads((a.source/'SOURCE_REVISION.json').read_bytes())['commit']
    plan = {'schema_version': 'bounded-skills/6', 'training': False, 'confirmation': False,
        'source_commit': revision, 'sampling_source_commit': parent['source_commit'],
        'vla_options_v2': True, 'sam_entry': parent['sam_entry'], 'jobs': jobs,
        'parent_plan': ref(a.parent_plan), 'parent_results': str(a.parent_results.resolve()),
        'registered_parent_cases': 40, 'missing_parent_cases': missing,
        'selection': 'best measured complete path from locally sampled prefixes and native-complete VLA suffixes',
        'domain': 'D2_eval_only', 'no_new_fork_sampling': True}
    a.output.mkdir(parents=True, exist_ok=False)
    (a.output/'manifest.json').write_text(json.dumps(plan, indent=2)+'\n')
    (a.output/'selections.json').write_text(json.dumps(selections, indent=2)+'\n')
    print(json.dumps({'output': str(a.output), 'cases': len(jobs), 'missing': missing,
        'selected_native_complete_paths': sum(j['path_selection']['reason'] == 'measured_native_complete_path' for j in jobs)}))


if __name__ == '__main__':
    main()
