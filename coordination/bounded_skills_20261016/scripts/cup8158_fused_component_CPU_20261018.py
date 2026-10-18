"""Trace current public cup membership through each geometric cleanup stage."""
# ruff: noqa: E402 -- choose immutable source and CPU before imports
import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
source = 'bc160ff'
sys.path.insert(0, str(root/f'source_bounded_{source}_20261018'))
import numpy as np
from scipy.spatial import cKDTree
from robots.libero.bounded_skills import MeasuredSkillAdapter
from robots.libero.bounded_self_filter import gripper_visual_boxes
from robots.libero.v5_geometric_grasp import panda_geometry

base = root/'results/bounded_skills/feasibility_20261017'
directory = next((base/'job8158_60').glob('*oracle*'))
choices = directory/'choices.jsonl'
rows = [json.loads(line) for line in choices.open()]
row, key = rows[16], 'e6'
robot = rows[15]['execution_details'][-1]['execution']['trace'][-1]['after']
for name in ('eef_xyz_m', 'eef_quat_xyzw'):
    np.testing.assert_allclose(robot[name], row['request']['robot'][name], atol=1e-10)
anchor = next(a for a in row['request']['anchors'] if a['id'] == key)
centre, size = np.asarray(anchor['xyz_m']), np.asarray(anchor['size_m'])
entity = SimpleNamespace(id=key, name=anchor['label'], part_of=None,
    lower=centre-size/2, upper=centre+size/2)
def load(path):
    path = Path(path)
    if path.suffix == '.json':
        return json.loads(path.read_text())
    with np.load(path) as z:
        return z[z.files[0]]
views = {}
step = row['public_geometry_evidence']['bounded_screen_e6_1_scene']['capture_step']
for camera, ref in row['perception_evidence'][key]['sam_mask_files'].items():
    world = load(directory/(camera+'_world_high.npz')/(f'{step:02d}.npz'))
    mask = load(ref['path']).astype(bool)
    views[camera] = {'source_step': step, 'xyz_world': world[mask]}
obs = {'robot0_eef_pos': robot['eef_xyz_m'], 'robot0_eef_quat': robot['eef_quat_xyzw'],
    'robot0_gripper_qpos': robot['finger_positions_m'], 'robot0_joint_pos': robot['joint_positions_rad']}
xml = root/'.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml'
a = MeasuredSkillAdapter.__new__(MeasuredSkillAdapter)
a.p = SimpleNamespace(env=SimpleNamespace(raw_obs=lambda: obs))
a.geometry = {**panda_geometry(xml), 'visual_boxes': gripper_visual_boxes(str(xml))}
a.robot_xml = xml.parent.parent/'robots/panda/robot.xml'
a._instance_cache, a._screen_cache, a._base_geometry = {}, {}, None
a.held = a.active = a.payload_reference = a.withdrawal_contact = None
a.instance_boundary_evidence, a.committed_grasps, a.plans = {}, {}, {}
a.record_public_geometry = False
a.scene = SimpleNamespace(entities={key: entity}, measurement_clouds_by_view={key: views}, measurement_clouds={})
a.ex = SimpleNamespace(toolkit=SimpleNamespace(_state=SimpleNamespace(latest_step=step,
    load=lambda name: load(directory/name/(f'{step:02d}'+Path(name).suffix)))))
block = next(d for d in row['candidate_screen_diagnostics'] if d.get('skill') == 'carry_to'
    and d.get('parameters', {}).get('target_id') == 'e99')
point = np.asarray(block['obstacle_point'])
stages = []
import robots.libero.bounded_skills as module
for name in ('clean_object_mask', 'complete_instance_boundary', 'complete_planar_boundary',
             'complete_sparse_instance_boundary', 'complete_crossview_boundary', 'retain_crossview_semantic_fragments'):
    original = getattr(module, name)
    def traced(world, *args, _name=name, _original=original, **kwargs):
        mask, evidence = _original(world, *args, **kwargs)
        pixels = np.asarray(world)[mask & np.isfinite(world).all(axis=2)]
        valid = np.asarray(world)[np.isfinite(world).all(axis=2)]
        stages.append({'function':_name, 'view_nearest_blocker_m':float(cKDTree(valid).query(point)[0]),
            'nearest_member_m':float(cKDTree(pixels).query(point)[0]) if len(pixels) else None,
            'member_pixels':len(pixels)})
        return mask, evidence
    setattr(module, name, traced)
a._cloud_and_ik()
instance = a._instance_pixels(key)
# Diagnose cross-view 3-D continuity using exactly the existing 3 mm limit.
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
scene = a._base_geometry[0]
lower, upper = instance.min(0), instance.max(0)
inside = ((scene >= lower) & (scene <= upper)).all(axis=1)
cloud = scene[inside]
reference_dir = directory/'bounded_payload_reference_scene.npz'
references = sorted((q for q in reference_dir.glob('*.npz') if int(q.stem) <= step),
    key=lambda q:int(q.stem))
static_path = references[-1]
static = load(static_path)
cloud = cloud[cKDTree(static).query(cloud)[0] > .004]
voxel, ids, inverse = np.unique(np.floor(cloud/.001).astype(int),axis=0,return_index=True,return_inverse=True)
pairs = cKDTree(cloud[ids]).query_pairs(.003,output_type='ndarray')
graph = coo_matrix((np.ones(len(pairs),dtype=np.uint8),(pairs[:,0],pairs[:,1])),shape=(len(ids),len(ids))).tocsr()
_, labels = connected_components(graph,directed=False)
seed = cKDTree(instance).query(cloud)[0] <= 1e-6
supported = np.unique(labels[np.unique(inverse[seed])])
member = np.isin(labels[inverse],supported)
complete = cloud[member]
graph_evidence = {'scope':'CPU hypothesis only;unchanged3mm 3D continuity,current bounds,4mm prelift static veto',
    'static_reference':str(static_path),'current_scene_points':len(scene),'bounded_nonstatic_points':len(cloud),
    'one_mm_voxels':len(ids),'three_mm_edges':len(pairs),'seed_points':int(seed.sum()),
    'retained_points':len(complete),'nearest_blocker_m':float(cKDTree(complete).query(point)[0])}

blockers = np.unique(np.array([d['obstacle_point'] for d in row['candidate_screen_diagnostics']
    if d.get('skill') == 'carry_to' and d.get('obstacle_point')]), axis=0)
report = {'scope': 'current RGB-D membership only; temporal payload path deliberately not reconstructed',
    'source': source, 'row':16, 'private_truth_used':False, 'gpu_used':False, 'training':False,
    'choices_sha256':hashlib.sha256(choices.read_bytes()).hexdigest(),
    'point_count':len(instance), 'blockers':blockers.tolist(),
    'nearest_instance_m':cKDTree(instance).query(blockers)[0].tolist(),
    'three_dimensional_component':graph_evidence, 'stages':stages, 'boundary':a.instance_boundary_evidence}
p = root/'coordination/bounded_skills_20261016/reports/cup8158_fused_component_CPU_20261018.json'
p.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='boundary'}),flush=True)
