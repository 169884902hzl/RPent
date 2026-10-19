"""Screen public-kinematic joint guides to measured precontact entries plus straight contact.

This does not relax numerical IK or collision checks and executes no physics.
The guide only supplies Cartesian waypoints to the existing full-route screen.
"""
import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root / 'source_bounded_chunk_v3_current_handle_20261019_ede83b18'
sys.path.insert(0, str(source))

import numpy as np
from scipy.spatial.transform import Rotation

from robots.libero.bounded_motion import SmoothMotion, measured_robot
from robots.libero.bounded_offline_labels import load_annotation_state
from robots.libero.v5_grasp_kinematics import forward_jacobian

choices, = (root / 'results/bounded_skills/feasibility_20261017/job9611_120').glob(
    '*oracle_k4/choices.jsonl')
row = [json.loads(line) for line in choices.read_text().splitlines()][1]
ref = row['private_prefix_annotation_state']
adapter = load_annotation_state(ref['path'], ref['sha256'])['adapter']
diagnostic, = (d for d in row['candidate_screen_diagnostics']
              if d.get('stage') == 'measured_surface_contact' and d.get('anchor_id') == 'e114')
screen = adapter._cloud_and_ik('e114', contact=True)
start = np.asarray(measured_robot(adapter.p)['joint_positions_rad'])
started = time.perf_counter()
proposals = []
seen = set()
for candidate in diagnostic['candidates']:
    quat = tuple(candidate['quat_xyzw'])
    if quat in seen:
        continue
    seen.add(quat)
    ik = copy.deepcopy(screen.ik)
    ik.route_joint_step_rad = None
    ik.last_solution = None
    ik.cache = {}
    entry = np.asarray(candidate['xyz_m']) + np.asarray(candidate['normal_xyz'])*.04
    endpoint = ik.check(entry, quat)
    for solve in endpoint['solves']:
        if solve['solution_found']:
            goal = np.asarray(solve['joint_positions_rad'])
            proposals.append((float(np.linalg.norm(goal-start)), candidate, goal, entry))
            break

records = []
for distance, candidate, goal, entry in sorted(proposals, key=lambda item: item[0]):
    route = []
    # Joint interpolation is a route proposal, not a reachability certificate.
    samples = max(2, int(np.ceil(np.max(np.abs(goal-start))/.04)))
    for fraction in np.linspace(0, 1, samples+1)[1:]:
        joints = start+(goal-start)*fraction
        pose, site, _ = forward_jacobian(screen.ik.nodes, joints, screen.ik.site_offset)
        route.append({'xyz_m': (screen.ik.world_offset+screen.ik.world_rotation@site).tolist(),
            'quat_xyzw': Rotation.from_matrix(screen.ik.world_rotation@pose[:3, :3]).as_quat().tolist()})
    # Preserve a 4 cm precontact entry and an independently screened descent.
    route.append({'xyz_m': entry.tolist(), 'quat_xyzw': candidate['quat_xyzw']})
    route.append({'xyz_m': candidate['xyz_m'], 'quat_xyzw': candidate['quat_xyzw']})
    before = time.perf_counter()
    _, _, _, evidence = SmoothMotion(adapter.p, screen, adapter.config).prepare(route)
    records.append({'yaw_deg': candidate['yaw_deg'], 'joint_distance_rad': distance, 'precontact_standoff_m': .04,
        'route': route, 'screen': evidence, 'screen_cpu_s': time.perf_counter()-before})
    if evidence['passed']:
        break

report = {'scope': 'CPU measured-contact kinematic route proposals; no physical success claim',
    'source_commit': 'ede83b18', 'context': ref,
    'choices_sha256': hashlib.sha256(choices.read_bytes()).hexdigest(), 'row': 1,
    'proposals': len(proposals), 'records': records,
    'cpu_s': time.perf_counter()-started, 'physics_steps': 0, 'rpc_calls': 0,
    'gpu_used': False, 'training': False,
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
out = root / 'coordination/bounded_skills_20261016/reports/microwave9611_joint_entry_CPU_20261019.json'
with out.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
print(json.dumps({'output': str(out), 'proposals': len(proposals),
    'screened': len(records), 'passed': sum(r['screen']['passed'] for r in records),
    'cpu_s': report['cpu_s']}))
