"""Compare voxel representatives on saved RGB-D pixels without simulation."""
import argparse
import hashlib
import importlib.util
import json
import time
from pathlib import Path

import numpy as np


def load_voxel(source, name):
    path = source/'robots/libero/v5_geometric_grasp.py'
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._voxel, hashlib.sha256(path.read_bytes()).hexdigest()


def compare(before, after, episodes, repeats):
    old, old_sha = load_voxel(before, 'voxel_before')
    new, new_sha = load_voxel(after, 'voxel_after')
    rows = []
    for episode in episodes:
        for camera in ('agentview', 'wrist'):
            # Fixed first three saved captures; no outcome-dependent selection.
            for path in sorted((episode/(camera+'_world_high.npz')).glob('*.npz'))[:3]:
                with np.load(path) as archive:
                    points = archive[archive.files[0]].reshape(-1, 3)
                for size in (.002, .004):
                    expected, actual = old(points, size), new(points, size)
                    assert np.array_equal(expected, actual), str(path)
                    samples = {'before': [], 'after': []}
                    for repeat in range(repeats):
                        order = [('before', old), ('after', new)]
                        for name, function in order[::1 if repeat % 2 == 0 else -1]:
                            start = time.perf_counter()
                            result = function(points, size)
                            samples[name].append(time.perf_counter()-start)
                            assert np.array_equal(expected, result)
                    rows.append(dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                        input_points=len(points), retained_points=len(expected), voxel_size_m=size,
                        pointwise_identical=True, retained_array_sha256=hashlib.sha256(expected.tobytes()).hexdigest(),
                        timings_s=samples, median_s={key: float(np.median(value)) for key, value in samples.items()}))
    assert rows, 'no saved public RGB-D arrays found'
    return dict(scope='CPU saved-public-pixel voxel identity and microbenchmark; no simulation or inference',
        before_source=str(before), after_source=str(after), before_module_sha256=old_sha,
        after_module_sha256=new_sha, comparisons=len(rows), all_pointwise_identical=True,
        repeats=repeats, rows=rows, GPU_used=False, training=False, confirmation=False,
        limitation='Microbenchmark timing is not a complete-episode speed measurement.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    parser.add_argument('--episode', type=Path, action='append', required=True)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = compare(args.before, args.after, args.episode, args.repeats)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({key: report[key] for key in ('comparisons', 'all_pointwise_identical', 'GPU_used')}))
