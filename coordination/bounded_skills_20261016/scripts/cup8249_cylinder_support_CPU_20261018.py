"""Test a public measured-cylinder hypothesis; no ownership changes or controls."""
import hashlib
import json
import os
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
d = next((root/'results/bounded_skills/feasibility_20261017/job8249_60').glob('*oracle*'))
r = json.loads((d/'choices.jsonl').read_bytes().splitlines()[12])
with np.load(d/'bounded_screen_e6_1_payload_local.npz/13.npz') as z:
    p = z[z.files[0]]
robot = r['request']['robot']
p = p@Rotation.from_quat(robot['eef_quat_xyzw']).as_matrix().T+robot['eef_xyz_m']
q = np.unique(np.array([b['obstacle_point'] for b in r['candidate_screen_diagnostics']
    if b.get('skill') == 'carry_to' and b.get('obstacle_point')]), axis=0)
centre = np.median(p, axis=0)
p = p-centre
q = q-centre
def residual(parameters, points):
    # Axis point is anchored to the measured centroid's z-plane.
    axis = np.r_[parameters[2:4], 1.]
    axis /= np.linalg.norm(axis)
    offset = points-np.r_[parameters[:2], 0.]
    radial = offset-np.outer(offset@axis, axis)
    return np.linalg.norm(radial, axis=1)-parameters[4]
fits = []
for initial in ([0., 0., 0., 0., .035], [0., 0., .3, 0., .035], [0., 0., 0., .3, .035]):
    fit = least_squares(residual, initial, args=(p,), loss='soft_l1', f_scale=.001,
        bounds=([-.1, -.1, -2., -2., .005], [.1, .1, 2., 2., .1]), max_nfev=300)
    error = residual(fit.x, p)
    fits.append({'success': bool(fit.success), 'parameters': fit.x.tolist(),
        'source_points': len(p), 'cost': fit.cost, 'residual_quantiles_m': np.quantile(abs(error), [.5, .75, .9, .95]).tolist(),
        'fraction_within_1mm': float((abs(error) <= .001).mean()),
        'blocker_residual_m': residual(fit.x, q).tolist()})
report = {'scope': 'CPU hypothesis only; no ownership change or control',
    'private_truth_used': False, 'gpu_used': False, 'training': False,
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'fits': fits}
(base/'reports/cup8249_cylinder_support_CPU_20261018.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
