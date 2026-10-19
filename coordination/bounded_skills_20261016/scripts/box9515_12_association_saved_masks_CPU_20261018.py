"""Replay held-ID association from saved public masks, depth and proprioception."""
# ruff: noqa: E402 -- choose CPU and the immutable source first
import copy
import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = root/'source_bounded_chunk_v3_directional_contact_20261018_4db4ea4'
sys.path.insert(0, str(source))
import numpy as np
from scipy.spatial.transform import Rotation

from robots.libero.bounded_offline_labels import load_annotation_state
from robots.libero.v5_runtime import MeasuredScene
from rpent.robots.components.sam3_client import Sam3Client

directory, = (root/'results/bounded_skills/feasibility_20261017/job9515_12').glob('*oracle_k4')
rows = [json.loads(line) for line in (directory/'choices.jsonl').read_bytes().splitlines()]
states = [load_annotation_state(r['private_prefix_annotation_state']['path'],
    r['private_prefix_annotation_state']['sha256'])['adapter'] for r in (rows[1], rows[2])]
step = states[1].ex.toolkit._state.latest_step
inputs = []
def load(name):
    path = directory/name/(f'{step:02d}'+Path(name).suffix)
    raw = path.read_bytes()
    inputs.append({'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest()})
    if path.suffix == '.json':
        return json.loads(raw)
    if path.suffix == '.npz':
        with np.load(path) as archive:
            return archive[archive.files[0]]
    return raw
masks = {}
for key in ('e35', 'e85'):
    for camera, ref in rows[2]['perception_evidence'][key]['sam_mask_files'].items():
        path = Path(ref['path']);raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == ref['sha256']
        inputs.append(ref)
        with np.load(path) as archive:
            mask = archive[archive.files[0]].astype(bool)
        masks.setdefault(camera, []).append({'mask': mask, 'score': states[1].scene._scores[key]})
images = {camera: load(camera+'_high.png') for camera in ('agentview', 'wrist')}
import base64
def segment(method, *, kwargs, **unused):
    assert method == 'sam3.segment_all'
    camera, = [name for name, image in images.items()
        if image == base64.b64decode(kwargs['image_base64'])]
    return {'instances': masks[camera]}
Sam3Client._decode_result = staticmethod(lambda item: SimpleNamespace(mask=item['mask']))
with np.load(directory/'bounded_payload_reference_target.npz/03.npz') as archive:
    points = archive[archive.files[0]]
prior_robot = json.loads((directory/'bounded_payload_reference_robot.json/03.json').read_text())
robot = rows[2]['request']['robot']
predicted = ((points-prior_robot['eef_xyz_m'])@Rotation.from_quat(prior_robot['eef_quat_xyzw']).as_matrix())
predicted = predicted@Rotation.from_quat(robot['eef_quat_xyzw']).as_matrix().T+robot['eef_xyz_m']
association = {'e35': tuple(np.median(predicted, axis=0))}
flags = json.loads((directory/'public_scene_flags.json').read_text())
flags['record_sam_masks_v6'] = False  # Never overwrite the saved mask artifacts.
results = []
for name, cls, kwargs in [('baseline', MeasuredScene, {}),
        ('transport_prior', MeasuredScene, {'association_positions': association})]:
    scene = cls(SimpleNamespace(_state=SimpleNamespace(latest_step=step,
        load=load, load_bytes=load)), SimpleNamespace(call=segment), 2, **flags)
    scene.entities = copy.deepcopy(states[0].scene.entities)
    scene._scores = copy.deepcopy(states[0].scene._scores)
    scene._ids = [key for key in scene._ids if key not in scene.entities]
    scene.refresh(['cream cheese'], **kwargs)
    entities = [e for e in scene.entities.values() if e.name == 'cream cheese' and e.visible]
    results.append({'method': name, 'entities': [dict(id=e.id, xyz=e.xyz, lower=e.lower,
        upper=e.upper, source_step=e.source_step) for e in entities],
        'held_identity_evidence': scene.perception_evidence.get('e35', {})})
    print(json.dumps({'method': name, 'entities': results[-1]['entities']}), flush=True)
report = {'job': '9515_12', 'before_row': 1, 'after_row': 2, 'association_positions': association,
    'results': results, 'inputs': inputs, 'runtime_sha256': hashlib.sha256((source/'robots/libero/v5_runtime.py').read_bytes()).hexdigest(),
    'source': str(source), 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'scope': 'Saved final-mask association replay, not a complete SAM RPC replay or physical execution',
    'physics_steps': 0, 'gpu_used': False, 'rpc_calls': 0, 'private_truth_used': False,
    'private_status_consumed': False, 'training': False, 'confirmation': False}
output = root/'coordination/bounded_skills_20261016/reports/box9515_12_association_saved_masks_CPU_20261018.json'
with output.open('x') as stream:
    json.dump(report, stream, indent=2)
    stream.write('\n')
