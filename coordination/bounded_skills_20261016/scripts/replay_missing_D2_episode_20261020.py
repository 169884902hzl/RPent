"""Execute a previously omitted selected-method replay from its saved initial state."""

import argparse
import hashlib
import importlib.util
import json
import os
import pickle
import sys
import time
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_bytes())


def ref(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--worker', type=Path, required=True)
    parser.add_argument('--parent-output', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    worker = read(args.worker)
    original = worker['result']
    assert worker['exit_code'] == 0 and original['status'] == 'physical_result'
    assert not original['training'] and original['actual_full_replay_success'] is False
    existing = original['full_replay']
    assert all(trial['success'] is True for trial in existing)
    origin = read(args.worker.parents[2]/'launch.json')
    assert Path(origin['source']).resolve(strict=True) == source
    assert origin['source_commit'] == original['source_commit']
    case = worker['case']
    folder = args.worker.parent/case['name']
    case_result = folder/'summary.json'
    assert read(case_result) == original
    assignment = read(args.worker.parent/'assignment.json')
    assert ref(assignment['manifest']['path']) == assignment['manifest']
    manifest = read(assignment['manifest']['path'])
    assert len(manifest['cases']) == 40 and not manifest['training'] and not manifest['confirmation']
    assert case in manifest['cases'] and manifest['source_commit'] == original['source_commit']
    private_plan = read(folder/'private_subtask_plan.json')
    assert not private_plan['unsupported']
    assert ref(private_plan['initial']['path'])['sha256'] == private_plan['initial']['sha256']
    selected = []
    for row in original['subtasks']:
        selection = row['selection']
        assert selection['status'] in {'measured', 'both_failed'}
        assert selection['method'] in {'self', 'call_vla'}
        assert selection['status'] != 'both_failed' or selection['method'] == 'self'
        selected.append({'subtask': row['subtask'], 'method': selection['method'],
            'sampled_status': selection['status']})
    assert selected
    seed_base = manifest['trial_seed_base']+1000000000+1000000*manifest['cases'].index(case)
    previous = -1
    for trial in existing:
        positions = [i for i, choice in enumerate(selected) if choice['subtask'] == trial['subtask']]
        assert len(positions) == 1 and positions[0] > previous
        previous = positions[0]
        assert trial['method'] == selected[previous]['method']
        assert trial['trial_seed'] == seed_base+10000*previous
        assert ref(trial['endpoint']['path'])['sha256'] == trial['endpoint']['sha256']
    assert previous < len(selected)-1
    resume = existing[-1]['endpoint'] if existing else private_plan['initial']
    plan = {'version': 'D2-independent-replay-supplement/1', 'case': case,
        'source_commit': original['source_commit'], 'source': str(source),
        'source_worker': ref(args.worker), 'original_case_result': ref(case_result),
        'initial': private_plan['initial'], 'subtask_plan': ref(folder/'private_subtask_plan.json'),
        'manifest': assignment['manifest'], 'selected': selected, 'script': ref(__file__),
        'trial_seed_base': seed_base, 'existing_replay_prefix': existing,
        'resume_from': resume, 'resume_after_selected_index': previous,
        'budget': manifest['budget'], 'training': False, 'confirmation': False,
        'scope': 'one omitted independent replay; includes the registered self tie when both sampled methods failed; no original record replacement'}
    if args.preflight:
        args.output.mkdir(parents=True)
        with (args.output/'plan.json').open('x') as stream:
            json.dump(plan, stream, indent=2)
            stream.write('\n')
        print(json.dumps({'preflight': 'passed', 'plan': ref(args.output/'plan.json'),
            'selected': selected}), flush=True)
        return 0
    assert read(args.output/'plan.json') == plan
    parent = read(args.parent_output/'launch.json')
    assert parent['slurm_job_id'] == os.environ['SLURM_JOB_ID']
    assert parent['cuda_visible_devices'] == os.environ['CUDA_VISIBLE_DEVICES']
    sys.path.insert(0, str(source))
    os.environ['LIBERO_TYPE'] = 'pro'
    os.environ['LIBERO_GRASP_DIAGNOSTIC_MODELS'] = str(args.output/'private_grasp_models')
    hooks_path = source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py'
    spec = importlib.util.spec_from_file_location('replay_owned_hooks', hooks_path)
    hooks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hooks)
    hooks.bootstrap_source('d2')
    hooks.install_d2_restore_compatibility()
    hooks.install_d2_spawn_bootstrap()
    from scripts import probe_bounded_hybrid_d2 as probe
    from rpent.utils.rpc.http_rpc import HttpRpcClient

    hooks.install_d2_request_compatibility(probe)
    endpoints = read(next(args.parent_output.glob('N*/*/assignment.json')))
    endpoints = {name: HttpRpcClient(endpoints[name+'_url']) for name in ('sam3', 'vla')}
    episode = args.output/'episode'
    episode.mkdir()
    started = time.perf_counter()
    with probe.runtime(case, endpoints, episode) as (facade, adapter, policy, timings):
        saved = pickle.loads(Path(plan['initial']['path']).read_bytes())
        probe.restore_checkpoint(facade, adapter, policy, saved)
        initial_hash = probe.snapshot_digest(facade.snapshot())
        assert initial_hash == plan['initial']['physics_sha256']
        if existing:
            saved = pickle.loads(Path(resume['path']).read_bytes())
            probe.restore_checkpoint(facade, adapter, policy, saved)
            assert probe.snapshot_digest(facade.snapshot()) == resume['physics_sha256']
        env = adapter.p.env
        original_step = env.step

        def step(*values, **options):
            before = env.execution_budget()['used_sim_steps']
            result = original_step(*values, **options)
            after = env.execution_budget()['used_sim_steps']
            physical = args.output/'first_physical_request.json'
            if after > before and not physical.exists():
                probe.write(physical, {'sim_steps_before': before, 'sim_steps_after': after,
                    'source_commit': plan['source_commit'], 'training': False})
            return result

        env.step = step
        trials = list(existing)
        decisions = sum(trial['decisions'] for trial in existing)
        for index, choice in enumerate(selected):
            if index <= previous:
                continue
            if env.terminated or env.truncated:
                break
            if facade.goal_status()['satisfied'][choice['subtask']['goal_index']]:
                continue
            with timings.measure('planning.request'):
                request = adapter.request(k=4)
            trial, endpoint = probe.trial(facade, adapter, policy, timings,
                choice['subtask'], choice['method'], plan['trial_seed_base']+10000*index,
                episode/f'replay_{index:02d}', request, decision_limit=plan['budget']['decisions']-decisions)
            trials.append(trial)
            decisions += trial['decisions']
            probe.restore_checkpoint(facade, adapter, policy, endpoint)
            if trial['success'] is not True:
                break
        native = bool(env.terminated or facade._native_success_events)
        known_methods = {choice['subtask']['id'] for choice in selected}
        complete_selection = all(item['id'] in known_methods for item in private_plan['subtasks'])
        actual = (True if native else False if (trials and trials[-1]['success'] is False)
            or complete_selection else None)
        result = {**plan, 'plan': ref(args.output/'plan.json'), 'full_replay': trials,
            'initial_physics_sha256': initial_hash, 'actual_full_replay_success': actual,
            'native_success_signal': native, 'registered_goal_predicate': facade.goal_status()['done'],
            'complete_selection': complete_selection, 'decisions': decisions,
            'sim_steps_used': env.execution_budget()['used_sim_steps'],
            'wall_s': time.perf_counter()-started,
            'wall_time_breakdown': timings.summary(time.perf_counter()-timings.started),
            'original_records_modified': False, 'status': 'physical_result'}
        probe.write(args.output/'summary.json', result)
    print(json.dumps({'case': case['name'], 'actual_full_replay_success': actual,
        'replayed_subtasks': len(trials), 'decisions': decisions,
        'summary': ref(args.output/'summary.json')}), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
