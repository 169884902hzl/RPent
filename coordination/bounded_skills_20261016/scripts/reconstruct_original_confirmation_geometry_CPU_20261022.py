"""Reconstruct known original confirmation geometry for exclusion only."""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import sys


def pinned(ref):
    raw = Path(ref['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref['sha256']:
        raise ValueError('registered exclusion input changed: '+ref['path'])
    return raw


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--registry', type=Path, required=True)
    p.add_argument('--registry-sha256', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    registry_ref = {'path': str(a.registry), 'sha256': a.registry_sha256}
    registry = json.loads(pinned(registry_ref))
    groups, unique = defaultdict(list), {}
    for ref in registry['original665']['source_plans']:
        plan = json.loads(pinned(ref))
        for row in plan['cases']:
            ep = row['episode']
            if ep['suite'] not in {'libero_spatial', 'libero_object', 'libero_goal', 'libero_10', 'libero_90'}:
                raise ValueError('non-original task in original confirmation registration')
            if row['state_sha256'] in unique:
                continue
            unique[row['state_sha256']] = row
            groups[row['bddl']['path']].append(row)
    expected = registry['counts']['official_original_confirmation_states']
    if len(unique) != expected:
        raise ValueError('registered unique original state count changed')
    os.environ['LIBERO_TYPE'] = 'standard'
    sys.path.insert(0, str(a.source.resolve(strict=True)))
    import robots.libero.env_server  # noqa: F401
    import numpy as np
    import torch
    from libero.libero.envs.env_wrapper import ControlEnv

    a.output.mkdir(parents=True, exist_ok=False)
    path = a.output/'original_confirmation_geometry.jsonl'
    completed = 0
    with path.open('x') as stream:
        for bddl, rows in sorted(groups.items()):
            pinned(rows[0]['bddl'])
            env = ControlEnv(bddl_file_name=bddl, use_camera_obs=False,
                has_offscreen_renderer=False, has_renderer=False, ignore_done=True)
            try:
                env.reset()
                cache = {}
                for row in rows:
                    init_ref = row['init_file']
                    if init_ref['path'] not in cache:
                        pinned(init_ref)
                        cache[init_ref['path']] = torch.load(init_ref['path'], weights_only=False)
                    index = row.get('official_init_index', row['episode']['seed'])
                    state = np.asarray(cache[init_ref['path']][index], dtype='<f8', order='C')
                    if hashlib.sha256(state.tobytes()).hexdigest() != row['state_sha256']:
                        raise ValueError('official initialization differs from registered confirmation state')
                    env.sim.set_state_from_flattened(state)
                    env.sim.forward()
                    positions = {name: np.array(env.sim.data.body_xpos[body], copy=True).tolist()
                        for name, body in env.env.obj_body_id.items()
                        if name in env.env.objects_dict}
                    if not positions or not all(np.isfinite(xyz).all() for xyz in positions.values()):
                        raise ValueError('registered object origins unavailable')
                    result = {'state_sha256': row['state_sha256'], 'episode': row['episode'],
                        'official_init_index': index, 'body_origins_world_m': positions,
                        'bddl': row['bddl'], 'init_file': init_ref,
                        'permanent_training_exclusion': True,
                        'coordinate_phase': 'registered_official_state_after_forward_without_controls'}
                    stream.write(json.dumps(result)+'\n')
                    completed += 1
                stream.flush()
                print(json.dumps({'completed': completed, 'registered': expected}), flush=True)
            finally:
                env.close()
    summary = {'registry': registry_ref, 'data': {'path': str(path),
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest()},
        'known_original_geometries': completed, 'registered_original_geometries': expected,
        'known_original_geometry_complete': completed == expected,
        'historical_registry_coverage_complete': registry['coverage']['coverage_complete'],
        'training_admission': False, 'policy_calls': 0, 'controls_executed': 0,
        'source_domain': 'explicitly_registered_official_original_initial_states',
        'scope': 'private geometry for permanent exclusion only; no outcomes or labels read'}
    (a.output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
