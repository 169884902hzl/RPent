"""Recompute both oracle arms from the same saved public RGB-D measurements.

No simulator, SAM service, controls, or historical selected IDs are used to
choose actions. Private task predicates are confined to BoundedOracle labels.
"""
import argparse
import copy
import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.update(CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--episode', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--decoded-request', type=Path)
args = parser.parse_args()
sys.path.insert(0, str(args.source))

import numpy as np

from robots.libero.bounded_oracle import BoundedOracle
from robots.libero.bounded_skills import MeasuredSkillAdapter
from robots.libero.v5_perception_geometry import fuse_cloud
from robots.libero.v5_state import Entity
from rpent.skill_package import VERSION
from rpent.skill_package.contract import compact_candidate, validate

ledger = args.episode/'choices.jsonl'
raw_line = ledger.read_bytes().splitlines()[0]
row = json.loads(raw_line)
historical = json.loads((args.episode/'private_oracle_labels.jsonl').read_text().splitlines()[0])
# Only the independent task status is an input; selected/acceptable sets are
# compared after both recomputations, never fed back into either selector.
private_status = historical['positions'][0]['evidence'][0]['initial_task_status']
inputs = {}


def load(path, expected_sha=None):
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha is not None:
        assert digest == expected_sha, str(path)+' changed'
    inputs[str(path)] = digest
    if path.suffix == '.json':
        return json.loads(raw)
    with np.load(path) as stream:
        return stream[stream.files[0]].copy()


def capture(name):
    return load(args.episode/name/('00'+Path(name).suffix))


worlds = {camera: capture(camera+'_world_high.npz') for camera in ('agentview', 'wrist')}
metadata = {camera: capture(camera+'_metadata.json') for camera in worlds}
rotation = np.asarray(metadata['agentview']['extrinsic_cam2world'])[:3, :3]
axes = []
for column in (0, 1):
    axis = rotation[:, column].copy()
    axis[2] = 0
    axes.append(tuple(float(round(x/np.linalg.norm(axis), 6)) for x in axis))

entities, measurements, views, recovered = {}, {}, {}, []
for anchor in row['request']['anchors']:
    key = anchor['id']
    evidence = row['perception_evidence'][key]
    points_by_view = {}
    for camera in evidence['source_cameras']:
        artifact = evidence['sam_mask_files'][camera]
        mask = load(Path(artifact['path']), artifact['sha256']).astype(bool)
        points = worlds[camera][mask].astype(np.float64)
        points_by_view[camera] = points[np.isfinite(points).all(1) & (np.abs(points).sum(1) > 1e-6)]
    primary = evidence['source_cameras'][0]
    points = points_by_view[primary]
    if evidence['fusion']['fused']:
        secondary = evidence['source_cameras'][1]
        points, joined, fusion = fuse_cloud(points,
            [(points_by_view[secondary], evidence['fusion']['secondary_score'])],
            trim_depth_tails='depth_filter' in evidence['fusion'])
        assert joined == 0 and fusion == evidence['fusion']
    assert evidence['shape_fit_version'] == 'none' and 'shape_completion' not in evidence
    lower, upper = np.quantile(points, (.02, .98), axis=0)
    centre = np.median(points, axis=0)
    centre_error = float(np.max(np.abs(centre-anchor['xyz_m'])))
    extent_error = float(np.max(np.abs(upper-lower-anchor['size_m'])))
    # The measured centre is a surface median, not a bounding-box midpoint.
    # Bounds are recovered from original mask pixels, never xyz +/- size/2.
    assert centre_error < 1e-12 and extent_error < 1e-12, (key, centre_error, extent_error)
    entities[key] = Entity(key, anchor['label'], tuple(centre), tuple(lower), tuple(upper), True, 0)
    measurements[key] = points
    views[key] = {camera: dict(source_step=0, xyz_world=value)
                  for camera, value in points_by_view.items()}
    recovered.append(dict(id=key, centre_max_error_m=centre_error, extent_max_error_m=extent_error,
                          lower=lower.tolist(), upper=upper.tolist(), points=len(points)))

initial = next(detail['execution']['trace'][0]['before'] for detail in row['execution_details']
               if detail.get('execution', {}).get('trace'))
assert initial['eef_xyz_m'] == row['request']['robot']['eef_xyz_m']
obs = dict(robot0_eef_pos=initial['eef_xyz_m'], robot0_eef_quat=initial['eef_quat_xyzw'],
           robot0_joint_pos=initial['joint_positions_rad'], robot0_gripper_qpos=initial['finger_positions_m'])
budget = dict(used_sim_steps=0, remaining_sim_steps=row['request']['remaining_sim_steps'])
xml = Path('/public/home/sunyihan/rpent_libero_eval/.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml')


def make_adapter(compact):
    env = SimpleNamespace(raw_obs=lambda: obs, execution_budget=lambda: budget.copy())
    scene = SimpleNamespace(entities=copy.deepcopy(entities), measurement_clouds=measurements,
        measurement_clouds_by_view=views, view_axes=tuple(axes), dual_view_fusion_v1=True,
        _scores={a['id']: a['confidence'] for a in row['request']['anchors']})
    state = SimpleNamespace(latest_step=0, load=capture)
    executor = SimpleNamespace(p=SimpleNamespace(env=env), scene=scene,
        instruction=row['request']['instruction'], toolkit=SimpleNamespace(_state=state))
    adapter = MeasuredSkillAdapter(executor, xml, allow_vla=False,
        compact_infeasible_candidates_v1=compact)
    for detail in row['candidate_screen_diagnostics']:
        if detail.get('stage') != 'grasp_route_search' or not detail['selected']:
            continue
        chosen = next(c for c in detail['candidates'] if c['id'] == detail['selected'])
        outward = np.asarray(chosen['approach_xyz'])-chosen['xyz']
        right, front = map(np.asarray, axes)
        directions = dict(above=np.array([0., 0., 1.]), front=front, left=-right, right=right)
        approach = max(directions, key=lambda name: np.dot(outward, directions[name]))
        adapter.plans[detail['anchor_id']] = dict(xyz_m=chosen['xyz'], quat_xyzw=chosen['body_quat_xyzw'],
            width_m=chosen['width_m'], quality=chosen['measurement_confidence'],
            approach_xyz_m=chosen['approach_xyz'], preferred_approach=approach,
            approach_route=[dict(xyz_m=w['xyz'], quat_xyzw=w['body_quat_xyzw']) for w in chosen['route'][:-1]],
            grasp_candidate_id=chosen['id'])
    return adapter


outputs = {}
full = copy.deepcopy(row['request'])
full.update(schema_version=VERSION, execution_prefix=None)
compact = copy.deepcopy(full)
compact['candidates'] = [compact_candidate(c) for c in full['candidates']]
requests = [('full', full), ('compact', compact)]
if args.decoded_request:
    decoded = load(args.decoded_request)
    assert [c['id'] for c in decoded['candidates']] == [c['id'] for c in full['candidates']]
    assert decoded['instruction'] == full['instruction']
    requests.append(('decoded', decoded))
for name, request in requests:
    validate(request)
    adapter = make_adapter(name != 'full')
    # Verify that recovered raw pixel inputs recreate the exact saved screens.
    screen_checks = []
    for key in (None, *entities):
        screen = adapter._cloud_and_ik(key)
        for suffix, actual in [('scene', screen.points), ('target', screen.target)]:
            artifact = row['public_geometry_evidence'][f'bounded_screen_{key}_0_{suffix}']
            expected = load(Path(artifact['path']), artifact['sha256'])
            assert np.array_equal(actual, expected), (name, key, suffix, actual.shape, expected.shape)
            screen_checks.append(dict(anchor_id=key, kind=suffix, exactly_equal=True, points=len(actual)))
    rpc = SimpleNamespace(call=lambda method: copy.deepcopy(private_status)
                          if method == 'oracle.status' else (_ for _ in ()).throw(ValueError(method)))
    oracle = BoundedOracle(rpc, adapter)
    decision = oracle.choose(request)
    labels = oracle.last_labels
    outputs[name] = dict(decision=decision, labels=labels, public_screen_checks=screen_checks,
                         private_trace=oracle.private_trace)
    args.output.with_name(args.output.stem+'_'+name+'_labels.json').write_text(json.dumps(labels, indent=2)+'\n')
    args.output.with_name(args.output.stem+'_'+name+'_request.json').write_text(json.dumps(request, indent=2)+'\n')

identity_keys = ('prefix', 'legal', 'selected', 'rule_acceptable', 'measured_success', 'measured_failure')
def label_sets(value):
    return [{key: position[key] for key in identity_keys} for position in value['labels']['positions']]

same = all(outputs['full']['decision']['candidate_ids'] == value['decision']['candidate_ids']
           for value in outputs.values())
same_sets = all(label_sets(outputs['full']) == label_sets(value) for value in outputs.values())
report = dict(scope='CPU fresh oracle selection and prefix planning on exact saved public RGB-D; no physical execution',
    source=str(args.source), script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    original_row_sha256=hashlib.sha256(raw_line).hexdigest(), input_sha256=inputs,
    recovered_entities=recovered, **outputs,
    same_selected=same, same_legal_acceptable_sets=same_sets,
    historical_selected=row['decision']['candidate_ids'],
    historical_selection_reproduced=outputs['full']['decision']['candidate_ids']==row['decision']['candidate_ids'],
    private_truth_scope='original task progress predicates only, isolated in oracle selector and audit labels',
    controls=0, fresh_sam_queries=0, training=False, confirmation=False, GPU_used=False)
args.output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(dict(output=str(args.output), selected=outputs['full']['decision']['candidate_ids'],
                     same_selected=same, same_sets=same_sets,
                     historical_selection_reproduced=report['historical_selection_reproduced'])))
assert same and same_sets
