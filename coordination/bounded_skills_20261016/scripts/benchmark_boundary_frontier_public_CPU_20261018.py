"""Compare exact boundary outputs and CPU time on captured public RGB-D."""
import argparse
import hashlib
import importlib.util
import json
import os
import time
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
import numpy as np
from scipy.spatial import cKDTree

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
parser = argparse.ArgumentParser()
parser.add_argument('--candidate-file', type=Path)
parser.add_argument('--output', type=Path, default=base/'reports/boundary_frontier_public_CPU_20261018.json')
args = parser.parse_args()
modules = []
sources = {}
for name in ('reference', 'frontier_candidate'):
    path = (args.candidate_file if name == 'frontier_candidate' and args.candidate_file
        else base/f'scripts/instance_boundary_{name}_20261018.py')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    modules.append(module)
    sources[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
directory = root/'results/bounded_skills/feasibility_20261017/job8862_140/microwave_open_libero_90_t35_s0_oracle_k4'
choices = directory/'choices.jsonl'
raw = choices.read_bytes()
row = json.loads(raw.splitlines()[3])
artifact = row['public_geometry_evidence']['bounded_screen_e99_1_target']
path = Path(artifact['path'])
assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact['sha256']
with np.load(path) as stored:
    reference = stored[stored.files[0]]
inputs = {str(path): artifact['sha256'], str(choices): hashlib.sha256(raw).hexdigest()}
results = []
for camera in ('agentview', 'wrist'):
    path = directory/(camera+'_world_high.npz')/'07.npz'
    inputs[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    with np.load(path) as stored:
        world = stored[stored.files[0]]
    valid = np.isfinite(world).all(axis=2)
    seed = np.zeros(valid.shape, bool)
    seed[valid] = cKDTree(reference).query(world[valid], distance_upper_bound=.001)[0] <= .001
    for kind in ('all_measured_target_seeds', 'left_half_of_measured_target_seeds'):
        mask = seed.copy()
        if kind.startswith('left_half'):
            mask[:, mask.shape[1]//2:] = False
        outputs, timings = [], []
        for module in modules:
            started = time.perf_counter()
            outputs.append(module.complete_instance_boundary(world, mask, rounds=sum(mask.shape)))
            timings.append(time.perf_counter()-started)
        assert np.array_equal(outputs[0][0], outputs[1][0]), (camera, kind)
        assert outputs[0][1] == outputs[1][1], (camera, kind)
        entry = dict(camera=camera, seed_rule=kind, shape=list(world.shape),
            seed_pixels=int(mask.sum()), completed_pixels=int(outputs[0][0].sum()),
            actual_rounds=len(outputs[0][1]['added_pixels_per_round']),
            exact_mask_and_evidence_equal=True,
            output_sha256=hashlib.sha256(outputs[0][0].tobytes()).hexdigest(),
            old_s=timings[0], candidate_s=timings[1])
        results.append(entry)
        print(json.dumps(entry), flush=True)
report = dict(scope='saved public RGB-D CPU boundary microbenchmark; seeds derived from measured table cloud',
    limitation='Half-frame seed restriction is a diagnostic workload, not the original runtime invocation; no full-episode speed claim.',
    inputs=inputs, sources=sources, results=results,
    private_truth_used=False, gpu_used=False, controls=0, training=False, confirmation=False,
    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
output = args.output
output.write_text(json.dumps(report, indent=2)+'\n')
