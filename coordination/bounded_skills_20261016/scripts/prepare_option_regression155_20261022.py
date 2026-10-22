"""Pin the original90/layout65 replay to their fully captured branch physics."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import pickle
import sys


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source))
    os.environ.setdefault('MUJOCO_GL', 'egl')
    os.environ.setdefault('PYOPENGL_PLATFORM', 'egl')
    import robots.libero.env_server
    from robots.libero.bounded_hybrid_diagnostic import snapshot_digest

    root = Path('/public/home/sunyihan/rpent_libero_eval')
    base = root/'results/bounded_skills/execution_repairs_20261022'
    rev = json.loads((args.source/'SOURCE_REVISION.json').read_bytes())['commit']
    out = base/('option_ceiling_20261022/regression155_'+rev[:8])
    sam = json.loads((base/'layout_runtime_c7520ae1/preparation/pilot20.json').read_bytes())['sam_entry']
    parents = [('original90', base/'qualified90_9716b68c/preparation/manifest.json',
        base/'qualified90_9716b68c/CPU_closed90_r1/positions.jsonl')]
    for packet in ('measured_packet1', 'measured_packet2'):
        directory = base/'layout_runtime_c7520ae1'/packet
        manifest = directory/'preparation/manifest.json'
        if not manifest.exists():
            manifest = directory/'manifest.json'
        parents.append((packet, manifest, directory/'CPU_closed_measured_r1/positions.jsonl'))
    jobs, registration = [], []
    for domain, manifest, positions in parents:
        plan = json.loads(manifest.read_bytes())
        by_name = {r['case']['name']: r for r in map(json.loads, positions.read_text().splitlines())}
        plan.update(source_commit=rev, parent_manifest=ref(manifest), training=False, confirmation=False)
        for original in plan['cases']:
            diagnostic = original['diagnostic']
            baseline = by_name[original['name']]
            checkpoint_ref = baseline['snapshot']
            path = Path(checkpoint_ref['path'])
            assert ref(path) == checkpoint_ref
            checkpoint = pickle.loads(path.read_bytes())
            physics = checkpoint['physics']
            assert {'integration', 'native_data', 'observation_state'} <= physics['actuator_state'].keys()
            physics_path = out/'complete_initials'/domain/(original['name']+'.pkl')
            physics_path.parent.mkdir(parents=True, exist_ok=True)
            with physics_path.open('xb') as stream:
                pickle.dump(physics, stream, protocol=5)
            diagnostic['original_subtask_start'] = copy.deepcopy(diagnostic['original_subtask_start'])
            diagnostic['original_subtask_start']['physics'] = ref(physics_path)
            registration.append({'case': original['name'], 'domain': domain,
                'record_id': baseline['record_id'], 'baseline_snapshot': checkpoint_ref,
                'baseline_complete_initial_physics_sha256': snapshot_digest(physics),
                'after_initial': ref(physics_path), 'private_coordinates_added_to_public_request': False})
        target = out/'preparation'/(domain+'_manifest.json')
        write(target, plan)
        jobs.extend({'kind': 'original_fork', 'case': case, 'manifest': ref(target)} for case in plan['cases'])
    assert len(jobs) == 155
    panel = {'schema_version': 'bounded-skills/6', 'source': str(args.source),
        'source_commit': rev, 'sam_entry': sam, 'training': False, 'confirmation': False,
        'vla_options_v2': True, 'jobs': jobs}
    write(out/'preparation/all155.json', panel)
    for shard in range(2):
        write(out/f'preparation/shard{shard}.json', dict(panel, jobs=jobs[shard::2]))
    write(out/'registration.json', {'states': 155, 'rows': registration,
        'protocol': 'same complete captured physics before fresh public reconstruction; same registered seeds/repeats/budgets',
        'source': rev, 'training': False, 'D2': False, 'PRO': False, 'confirmation': False})
    print(json.dumps({'output': str(out), 'states': 155, 'source': rev}))


if __name__ == '__main__':
    main()
