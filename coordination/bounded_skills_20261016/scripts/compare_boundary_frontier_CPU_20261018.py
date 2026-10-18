"""Check synchronous boundary outputs against the pre-optimization function."""
import hashlib
import importlib.util
import json
import time
from pathlib import Path

import numpy as np

root = Path(__file__).resolve().parents[3]
base = root/'coordination/bounded_skills_20261016'
paths = [base/'scripts/instance_boundary_reference_20261018.py', root/'robots/libero/v5_grasp_geometry.py']
modules = []
for index, path in enumerate(paths):
    spec = importlib.util.spec_from_file_location('boundary_'+str(index), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    modules.append(module)
rng = np.random.default_rng(71018)
rows = []
for shape in ((2, 4), (12, 16), (64, 80), (240, 320), (257, 263)):
    y, x = np.mgrid[:shape[0], :shape[1]]
    world = np.stack((x*.0008, y*.0008, .9+x*.00001), axis=-1)
    world[:, 3*shape[1]//4:, 2] += .02
    if shape[0] > 2:
        world[shape[0]//2, shape[1]//2] = np.nan
    for kind in ('stripe', 'random'):
        mask = ((x >= 2) & (x < 4)) if kind == 'stripe' else rng.random(shape) < .3
        for spacing in (False, True):
            outputs, timings = [], []
            for module in modules:
                started = time.perf_counter()
                outputs.append(module.complete_instance_boundary(world, mask,
                    rounds=sum(shape), measured_tangent_spacing=spacing))
                timings.append(time.perf_counter()-started)
            assert np.array_equal(outputs[0][0], outputs[1][0]), (shape, kind, spacing)
            assert outputs[0][1] == outputs[1][1], (shape, kind, spacing)
            rows.append(dict(shape=shape, seed=kind, measured_spacing=spacing,
                exact_mask_and_evidence_equal=True, old_s=timings[0], new_s=timings[1],
                rounds=len(outputs[0][1]['added_pixels_per_round'])))
report = dict(scope='synthetic CPU geometry regression, not task success', seed=71018,
    sources={str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
    rows=rows, training=False, confirmation=False, GPU_used=False, controls=0)
output = base/'reports/boundary_frontier_runtime_synthetic_CPU_20261018.json'
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(dict(cases=len(rows), all_outputs_exact=True, output=str(output))))
