"""Same-state simulation-only ingress forks; native contacts are output only."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pickle
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from types import SimpleNamespace


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest()}


def checked(value):
    path = Path(value['path']); assert ref(path) == value
    return path


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, default=lambda x:x.tolist() if hasattr(x,'tolist') else str(x))


def hand_contacts(contacts):
    """Describe contacts independently of the planner; never return an action."""
    result = {}
    for row in contacts:
        a, b = row['geom1'] or '', row['geom2'] or ''
        if ('gripper' in a) == ('gripper' in b): continue
        hand, other = (a, b) if 'gripper' in a else (b, a)
        if other.startswith(('robot', 'gripper')): continue
        pair = hand+' / '+other
        result[pair] = min(result.get(pair, 1.), row['distance_m'])
    return result


def worker(args, plan):
    os.environ['LIBERO_TYPE'] = 'standard'
    os.environ['LIBERO_CONFIG_PATH'] = str(checked(plan['libero_config']).parent)
    sys.path.insert(0, str(args.source))
    hooks = load_module(args.source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py', 'approach_hooks')
    hooks.bootstrap_source('original', evaluation='hybrid_repair')
    hooks.install_d2_restore_compatibility()
    from scripts import probe_bounded_hybrid_d2 as probe
    from scripts import probe_bounded_hybrid_repair as repair
    from robots.libero.bounded_motion import SmoothMotion
    from rpent.utils.rpc.http_rpc import HttpRpcClient
    helper = load_module(checked(plan['approach_helper']), 'approach_proposal')
    row = plan['jobs'][args.worker]; case = row['case']
    assignment = json.loads((args.output/'assignment.json').read_text())
    endpoints = {key: HttpRpcClient(assignment[key+'_url']) for key in ('sam3', 'vla')}
    saved = pickle.loads(checked(row['branchpoint']).read_bytes())
    start = repair.constructed_original_start(case, plan)
    episode = args.output/'episode'; episode.mkdir()
    with probe.runtime(case, endpoints, episode, domain='original', constructed_start=start) as (facade, adapter, policy, timings):
        results = []
        for arm in ('straight_no_veto', 'elevated_screened'):
            probe.restore_checkpoint(facade, adapter, policy, saved)
            initial = probe.snapshot_digest(facade.snapshot())
            candidate = adapter._candidate(row['component_skill'], row['component_parameters'], complete=True)
            if candidate is None: raise RuntimeError('saved selected public preparation is unavailable')
            adapter._commit_grasp(candidate)
            route = adapter._route(row['component_skill'], candidate['parameters'])
            if not route: raise RuntimeError('saved public stand-off route is unavailable')
            endpoint = copy.deepcopy(route[-1])
            screen = adapter._cloud_and_ik(candidate['parameters'].get('anchor_id', candidate['parameters'].get('target_id')))
            if arm == 'straight_no_veto':
                selected = [endpoint]
                # This bypass exists only in this explicitly authorized
                # simulation diagnostic. Production screens are untouched.
                screen_call = lambda poses: {'passed': True, 'reason': 'diagnostic_collision_veto_disabled',
                    'collision': None, 'ik_reachable': None, 'path_min_clearance_m': None}
                proposal = {'scope': 'simulation diagnostic only; no collision certificate'}
            else:
                selected, proposal = helper.elevated_approach(adapter.robot(), endpoint, screen)
                screen_call = screen
            before = facade.grasp_contacts()
            baseline = hand_contacts(before['contacts'])
            attached = [name for name, data in before['objects'].items() if data['dual_finger_contact']]
            contacts = []; original_step = adapter.p._step_env
            def step(action):
                original_step(action)
                measured = facade.grasp_contacts()
                contacts.append({'sim_time': measured['sim_time'], 'contacts': measured['contacts']})
            adapter.p._step_env = step
            try:
                motion = SmoothMotion(adapter.p, screen_call, adapter.config).run(selected,
                    gripper=adapter.gripper_command, blend=False)
            finally:
                adapter.p._step_env = original_step
            unexpected = {}; attached_pairs = {}
            for sample in contacts:
                for pair, distance in hand_contacts(sample['contacts']).items():
                    if distance >= -1e-6 or distance >= baseline.get(pair, 0.)-1e-6: continue
                    target = attached_pairs if any(name in pair for name in attached) else unexpected
                    target[pair] = min(target.get(pair, 1.), distance)
            result = {'arm': arm, 'initial_physics_sha256': initial, 'endpoint': endpoint,
                'waypoints': selected, 'proposal': proposal, 'motion': motion,
                'initial_hand_contacts': baseline, 'initial_dual_finger_objects': attached,
                'new_or_deeper_nonattached_hand_contacts': unexpected,
                'new_or_deeper_initially_grasped_object_contacts': attached_pairs,
                'native_contacts': contacts, 'private_contacts_used_for_action': False}
            write(args.output/(arm+'.json'), result)
            results.append({k: result[k] for k in ('arm','initial_physics_sha256','endpoint',
                'new_or_deeper_nonattached_hand_contacts') } | {
                'executed': motion.get('executed'), 'steps_used': motion.get('steps_used', 0),
                'stop_reason': motion['stop_reason'], 'endpoint_error_m': motion.get('endpoint_error_m'),
                'record': ref(args.output/(arm+'.json'))})
        assert results[0]['initial_physics_sha256'] == results[1]['initial_physics_sha256']
        assert results[0]['endpoint'] == results[1]['endpoint']
        write(args.output/'summary.json', {'case': case, 'old_rejection': row['old_rejection'],
            'arms': results, 'training': False, 'D2': False, 'PRO': False, 'confirmation': False,
            'source_commit': plan['source_commit'], 'entry_sha256': plan['entry_sha256'],
            'truth_definition': 'new or >1um deeper penetrating hand-scene geom pair; initial dual-finger objects reported separately; incomplete unchecked route is not a certified false positive'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--worker', type=int)
    args = parser.parse_args(); args.source = args.source.resolve(strict=True)
    plan = json.loads(args.manifest.read_text())
    assert not plan['training'] and not plan['confirmation']
    assert ref(Path(__file__))['sha256'] == plan['entry_sha256']
    if args.worker is not None: return worker(args, plan)
    os.environ['PYTHONPATH'] = str(args.source); os.chdir(args.source); sys.path.insert(0, str(args.source))
    hooks = load_module(args.source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py', 'approach_parent_hooks')
    hooks.bootstrap_source('original', evaluation='hybrid_repair')
    from scripts.probe_bounded_feasibility import services
    args.output.mkdir(parents=True, exist_ok=True)
    service = SimpleNamespace(source=args.source, output=args.output, sam3_entry=checked(plan['sam_entry']))
    def episode(index, endpoints):
        pointer = args.output/f'closed_{index:03d}.json'
        if pointer.exists(): checked(json.loads(pointer.read_text())); return str(pointer)
        directory = args.output/f'case{index:03d}'
        if directory.exists(): directory.rename(args.output/f'interrupted_{index:03d}_{time.time_ns()}')
        directory.mkdir(); write(directory/'assignment.json', {key+'_url':v._base_url for key,v in endpoints.items()})
        command = [sys.executable, str(Path(__file__).resolve()), '--source',str(args.source),
            '--manifest',str(args.manifest),'--output',str(directory),'--worker',str(index)]
        with (directory/'worker.log').open('x') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
        write(pointer, ref(directory/'summary.json')); return str(pointer)
    with hooks.owned_services(service, services, vla=True) as endpoints:
        with ThreadPoolExecutor(max_workers=8) as pool:
            pending = [pool.submit(episode, index, endpoints) for index in range(len(plan['jobs']))]
            for future in as_completed(pending): print(json.dumps({'closed':future.result()}),flush=True)


if __name__ == '__main__': main()
