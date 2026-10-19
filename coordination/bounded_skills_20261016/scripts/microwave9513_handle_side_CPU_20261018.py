"""Check a handle's measured protrusion side instead of camera-facing sign."""
# ruff: noqa: E402 -- choose CPU/source before optional simulator code
import copy
import argparse
import hashlib
import inspect
import json
import os
import sys
import textwrap
import time
from collections import Counter
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root/'source_bounded_chunk_v3_transport_identity_20261018_94db13e'
sys.path.insert(0, str(source))
import numpy as np
from scipy.spatial.transform import Rotation
from robots.libero.bounded_offline_labels import load_annotation_state
from robots.libero import bounded_skills

parser = argparse.ArgumentParser()
parser.add_argument('--direct', action='store_true')
args = parser.parse_args()
variant = None
if args.direct:
    script = (root/'coordination/bounded_skills_20261016/scripts/microwave9513_reentry_routes_CPU_20261018.py').read_text()
    fragment = script[script.index('original = bounded_skills.'):script.index('directory, = ')]
    namespace = dict(globals())
    exec(compile(fragment, '<direct-reentry-builder>', 'exec'), namespace)
    variant = namespace['variant']

directory, = (root/'results/bounded_skills/feasibility_20261017/job9513_120').glob('*oracle_k4')
rows = [json.loads(line) for line in (directory/'choices.jsonl').read_bytes().splitlines()]
records = []
for index in (6, 14):
    row = rows[index]
    reference = row['private_prefix_annotation_state']
    frozen = load_annotation_state(reference['path'], reference['sha256'])
    handle, = [x['measurement'] for x in row['candidate_screen_diagnostics']
        if x.get('stage') == 'fixture_contact_measurement' and x.get('anchor_id') == 'e114']
    search, = [x for x in row['candidate_screen_diagnostics']
        if x.get('stage') == 'fixture_route_search' and x.get('anchor_id') == 'e114']
    seed = search['candidates'][0]
    plan = {'xyz_m': seed['route'][-1]['xyz_m'], 'quat_xyzw': seed['route'][-1]['quat_xyzw'],
        'approach_xyz_m': seed['route'][-2]['xyz_m'], 'width_m': seed['width_m'],
        'handle_measurement': handle}
    face = row['fixture_measurement_evidence']['e98']['door_measurement']['instances'][0]['plane']
    normal = np.array([*face['normal_xy'], 0.])
    gap = float(normal[:2]@(np.array(handle['pose']['xyz'][:2])-face['centre'][:2]))
    assert max(.005, 2*face['residual_p90_m']) <= abs(gap) <= .06
    if gap < 0:
        normal = -normal
    old_normal = np.array(plan['approach_xyz_m'])-plan['xyz_m']
    old_normal /= np.linalg.norm(old_normal)
    assert abs(normal@old_normal) > .999
    corrected = copy.deepcopy(plan)
    orientation = Rotation.from_quat(plan['quat_xyzw'])
    if normal@old_normal < 0:
        orientation = Rotation.from_euler('z', np.pi)*orientation
    geometry = frozen['adapter'].geometry
    pad_centre = np.mean([(np.asarray(b['lower'])+b['upper'])/2 for b in geometry['boxes']
        if b['name'].endswith('_pad')], axis=0)
    site = orientation.as_matrix()@Rotation.from_euler('z', -np.pi/2).as_matrix()
    contact = np.asarray(handle['pose']['xyz'])-site@pad_centre
    corrected.update(xyz_m=contact.tolist(), quat_xyzw=orientation.as_quat().tolist(),
        approach_xyz_m=(contact+normal*.12).tolist())
    results = []
    for name, candidate_plan in [('baseline', plan), ('measured_handle_side', corrected)]:
        adapter = copy.deepcopy(frozen['adapter'])
        adapter.candidate_diagnostics = []
        assert not any(receipt['skill'] == 'descend' and receipt['outcome'] != 'success'
            for prior in rows[:index] for receipt in prior.get('receipts', []))
        adapter.failed_contact_poses = {}
        started = time.perf_counter()
        result = (variant(adapter, adapter.scene.entities['e114'], candidate_plan)
            if variant is not None and name == 'measured_handle_side' else
            adapter._screen_fixture_approaches(adapter.scene.entities['e114'], candidate_plan))
        diagnostic = adapter.candidate_diagnostics[-1]
        record = {'method': name, 'cpu_s': time.perf_counter()-started, 'plan': result,
            'diagnostic': diagnostic}
        results.append(record)
        print(json.dumps({'row': index, 'method': name, 'plan_available': result is not None,
            'cpu_s': record['cpu_s'], 'normal': normal.tolist(), 'handle_plane_gap_m': gap,
            'reasons': dict(Counter((x.get('screen') or {}).get('reason')
                for x in diagnostic['candidates']))}), flush=True)
    records.append({'row': index, 'context': reference, 'measured_backing_face': face,
        'measured_handle_pose': handle['pose'], 'original_approach_normal': old_normal.tolist(),
        'measured_handle_side_normal': normal.tolist(), 'handle_plane_gap_m': gap, 'results': results})
report = {'source': str(source), 'job': '9513_120', 'records': records, 'physics_steps': 0,
    'gpu_used': False, 'rpc_calls': 0, 'private_truth_used': False,
    'scope': 'Same measured handles, original whole-route collision/IK checks; no physical outcome',
    'training': False, 'confirmation': False, 'direct_routes': args.direct,
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
suffix = '_direct' if args.direct else ''
output = root/f'coordination/bounded_skills_20261016/reports/microwave9513_handle_side_CPU_20261018{suffix}.json'
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
