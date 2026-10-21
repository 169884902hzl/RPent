"""Compare complete sampler records on saved public clouds, without RPC/control."""
import argparse
import cProfile
import hashlib
import importlib.util
import json
import pickle
import pstats
import sys
import time
from pathlib import Path


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      default=lambda v: v.tolist()).encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--candidate-directory', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source.resolve(strict=True)))
    import numpy as np
    import robots.libero.v5_geometric_grasp as shared_geometry

    before_directory = args.source/'robots/libero'
    variants = {}
    for name, directory in (('before', before_directory), ('after', args.candidate_directory)):
        variants[name] = (load_module(name+'_geometry', directory/'v5_geometric_grasp.py'),
                          load_module(name+'_route', directory/'v5_grasp_route.py'))
    saved = pickle.loads(args.checkpoint.read_bytes())
    scene, adapter = (saved['public_runtime'][key] for key in ('scene', 'adapter'))
    raw = saved['physics']['actuator_state']['observation_state']['cache']
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    original_opposition = shared_geometry._opposition
    try:
        for key, points in scene['measurement_clouds'].items():
            if key not in scene['entities'] or len(points) < 40:
                continue
            entity = scene['entities'][key]
            row = {'anchor_id': key, 'name': entity.name, 'points': len(points),
                   'cloud_sha256': hashlib.sha256(np.asarray(points).tobytes()).hexdigest()}
            results = {}
            for name, (geometry, route) in variants.items():
                shared_geometry._opposition = geometry._opposition
                profile = cProfile.Profile()
                start = time.perf_counter()
                # Both ordinary and expanded sampling are part of the same
                # public contact catalogue; keep the per-surface fit cache.
                cache = {}
                def sample():
                    return [route.sample_unified_grasps(points, np.empty((0, 3)), entity.name,
                        raw['robot0_eef_pos'], raw['robot0_eef_quat'], adapter['geometry'], None,
                        float(raw['robot0_eef_pos'][2]), candidate_only=True,
                        include_band_seeds=expanded, opposition_cache=cache)
                        for expanded in (False, True)]
                result = profile.runcall(sample)
                elapsed = time.perf_counter()-start
                raw_result = canonical(result)
                results[name] = raw_result
                (args.output/f'{key}_{name}.json').write_bytes(raw_result)
                profile.dump_stats(str(args.output/f'{key}_{name}.pstats'))
                stats = pstats.Stats(profile)
                top = sorted(stats.stats.items(), key=lambda item: item[1][3], reverse=True)[:20]
                row[name] = {'wall_s': elapsed, 'result_sha256': hashlib.sha256(raw_result).hexdigest(),
                    'records': [len(group[1]) for group in result],
                    'top20': [{'file': k[0], 'line': k[1], 'function': k[2], 'calls': v[1],
                               'self_s': v[2], 'cumulative_s': v[3]} for k, v in top]}
            row['byte_equal'] = results['before'] == results['after']
            rows.append(row)
            print(json.dumps({k: v for k, v in row.items() if k not in ('before', 'after')}), flush=True)
    finally:
        shared_geometry._opposition = original_opposition
    manifest = {'checkpoint': str(args.checkpoint),
        'checkpoint_sha256': hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
        'source': str(args.source), 'candidate_directory': str(args.candidate_directory),
        'candidate_files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in args.candidate_directory.glob('*.py')},
        'scope': 'CPU saved public clouds; complete sampler records; not request/N1/physical results',
        'physics_steps': 0, 'rpc_calls': 0, 'rows': rows,
        'all_byte_equal': all(row['byte_equal'] for row in rows)}
    (args.output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    if not manifest['all_byte_equal']:
        raise RuntimeError('sampler records changed; retain outputs and investigate')


if __name__ == '__main__':
    main()
