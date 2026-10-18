"""Check a saved moving public surface without changing its 1cm guard."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, required=True)
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.source))

import numpy as np

from robots.libero.bounded_payload import stationary_surface_registration

base = args.root/'results/bounded_skills/feasibility_20261017/job8831_100/drawer_open_libero_goal_t0_s0_oracle_k4'
inputs = {}


def load(name, step):
    path = base/(name+'.npz')/(f'{step:02}.npz')
    raw = path.read_bytes()
    inputs[str(path)] = hashlib.sha256(raw).hexdigest()
    with np.load(path) as data:
        return data[data.files[0]].reshape(-1, 3)


reference = load('bounded_contact_e54_reference', 3)
current = load('bounded_contact_e54_reference', 4)
target = load('bounded_screen_e54_1_target', 4)
scene = load('bounded_screen_e54_1_scene', 4)
world = np.concatenate([scene, current, target])
checks = {str(delta): stationary_surface_registration(
    reference+[0., delta, 0.], world, current) for delta in (0., .02, .04)}
assert checks['0.02']['accepted']
assert not checks['0.0']['accepted'] and not checks['0.04']['accepted']
report = dict(scope='CPU saved public contact surfaces and screened RGB-D; no controls',
    source=str(args.source), inputs=inputs, before_points=len(reference), after_points=len(current),
    expected_translation_m=[0., .02, 0.], observed_axis_interval_m=[.018, .02], checks=checks,
    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    verifier_sha256=hashlib.sha256((args.source/'robots/libero/bounded_payload.py').read_bytes()).hexdigest(),
    training=False, GPU_used=False,
    limitations=['Uses saved public self-filtered and screened clouds, not a new physical replay.',
                 'The 0cm and 4cm predictions deliberately disagree with the observed 1.9cm movement.'])
args.output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(dict(output=str(args.output), accepted={key: value['accepted'] for key, value in checks.items()})))
