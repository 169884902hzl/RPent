# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
"""Rebuild held-instance depth membership without new segmentation or controls."""
# ruff: noqa: E402 -- pin the immutable source before importing robot modules
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.update(CUDA_VISIBLE_DEVICES="", OPENBLAS_NUM_THREADS="1")
parser = argparse.ArgumentParser()
parser.add_argument("--job", action="append", required=True)
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--row", type=int)
parser.add_argument("--output", type=Path)
parser.add_argument("--save-queries", action="store_true")
parser.add_argument("--sam-report", type=Path)
parser.add_argument("--compare-spatial-candidate", type=Path)
parser.add_argument("--candidate-skills", type=Path)
parser.add_argument("--screen-routes", action="store_true")
parser.add_argument("--registration-diagnostics", action="store_true")
parser.add_argument("--candidate-registration", type=Path)
args = parser.parse_args()
if args.registration_diagnostics and args.output is None:
    parser.error('--registration-diagnostics requires --output')
sys.path.insert(0, str(args.source))

import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

from robots.libero.bounded_motion import MotionConfig, SmoothMotion
from robots.libero.bounded_self_filter import gripper_visual_boxes
from robots.libero.bounded_skills import MeasuredSkillAdapter
from robots.libero.v5_geometric_grasp import panda_geometry
from robots.libero.v5_state import Entity

if args.candidate_skills:
    import importlib.util

    spec = importlib.util.spec_from_file_location('candidate_skills', args.candidate_skills)
    candidate_skills = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate_skills)
    MeasuredSkillAdapter = candidate_skills.MeasuredSkillAdapter

root = Path("/public/home/sunyihan/rpent_libero_eval")
spatial_comparison = []
registration_diagnostics = []
if args.candidate_registration:
    import importlib.util

    from robots.libero import bounded_payload

    spec = importlib.util.spec_from_file_location('candidate_registration', args.candidate_registration)
    candidate_registration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate_registration)
    bounded_payload._surface_registration = candidate_registration._surface_registration
if args.registration_diagnostics:
    from robots.libero import bounded_payload

    original_registration = bounded_payload._surface_registration

    def diagnose_registration(predicted, current):
        corrected, forward = original_registration(predicted, current)
        _, reverse = original_registration(current, predicted)
        record = {'predicted_points': len(predicted), 'current_points': len(current),
            'forward': forward, 'reverse': reverse}
        path = args.output.with_name(args.output.stem+f'_registration_{len(registration_diagnostics)}.npz')
        np.savez_compressed(path, predicted=predicted, current=current)
        record['public_inputs'] = {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        if reverse['accepted']:
            # Invert the measured-to-prior diagnostic fit. Check the entire
            # prior surface against the unchanged displacement constraint.
            source = np.asarray(current, float).reshape(-1, 3)
            source = source[np.isfinite(source).all(axis=1)]
            _, ids = np.unique(np.floor(source/.001).astype(int), axis=0, return_index=True)
            source = source[np.sort(ids)]
            source = source[::max(1, len(source)//8000)]
            centre = source.mean(0)
            restored = (np.asarray(predicted)-centre-reverse['translation_m'])@np.asarray(reverse['rotation_matrix'])+centre
            record['inverse_maximum_prior_displacement_m'] = float(np.linalg.norm(restored-predicted, axis=1).max())
            record['current_to_prior_median_before_m'] = float(np.median(cKDTree(predicted).query(current)[0]))
            record['current_to_prior_median_after_m'] = float(np.median(cKDTree(restored).query(current)[0]))
        registration_diagnostics.append(record)
        return corrected, forward  # Diagnostics never change membership.

    bounded_payload._surface_registration = diagnose_registration
if args.compare_spatial_candidate:
    import importlib.util
    import time

    from robots.libero import bounded_payload

    spec = importlib.util.spec_from_file_location('candidate_payload', args.compare_spatial_candidate)
    candidate_payload = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate_payload)
    original_spatial = bounded_payload.complete_spatial_payload_component

    def compare_spatial(points, seeds, stationary, lower, upper):
        inputs = (points, seeds, stationary, lower, upper)
        elapsed = {'baseline': [], 'candidate': []}
        for repeat in range(2):
            order = [('baseline', original_spatial),
                     ('candidate', candidate_payload.complete_spatial_payload_component)]
            if repeat:
                order.reverse()
            outputs = {}
            for label, function in order:
                start = time.perf_counter()
                outputs[label] = function(*inputs)
                elapsed[label].append(time.perf_counter()-start)
            np.testing.assert_array_equal(outputs['baseline'][0], outputs['candidate'][0])
            assert outputs['baseline'][1] == outputs['candidate'][1]
        spatial_comparison.append({'input_sha256': [hashlib.sha256(np.asarray(x).tobytes()).hexdigest()
            for x in inputs], 'input_shapes': [list(np.shape(x)) for x in inputs],
            'raw_seconds': elapsed, 'output_members_exact': True, 'evidence_exact': True,
            'evidence': outputs['baseline'][1]})
        return outputs['baseline']

    bounded_payload.complete_spatial_payload_component = compare_spatial
reports = []
for job in args.job:
    directory = next((root / "results/bounded_skills/feasibility_20261017" / ("job" + job)).glob("*oracle*"))
    prefix = (directory / "choices.jsonl").read_bytes().splitlines()
    rows = [json.loads(line) for line in prefix]
    row = (rows[args.row] if args.row is not None else
           next(row for row in rows if row["request"]["robot"]["held_anchor_id"]))
    index = row["index"]
    key = row["request"]["robot"]["held_anchor_id"]
    step = row["public_geometry_evidence"][f"bounded_screen_{key}_1_scene"]["capture_step"]
    robot = next(control["after"] for old in reversed(rows[:index])
                 for detail in reversed(old["execution_details"])
                 for control in reversed(detail.get("execution", {}).get("trace", [])))
    for field in ("eef_xyz_m", "eef_quat_xyzw"):
        np.testing.assert_allclose(robot[field], row["request"]["robot"][field], atol=1e-10)

    def load(path):
        path = Path(path)
        if path.suffix == ".json":
            return json.loads(path.read_text())
        if path.suffix == ".png":
            return np.asarray(Image.open(path))
        with np.load(path) as data:
            return data[data.files[0]]

    def frame(name):
        return load(directory / name / (f"{step:02d}" + Path(name).suffix))

    views = {}
    for camera, artifact in row["perception_evidence"][key]["sam_mask_files"].items():
        assert hashlib.sha256(Path(artifact["path"]).read_bytes()).hexdigest() == artifact["sha256"]
        views[camera] = {"source_step": step,
                         "xyz_world": frame(camera + "_world_high.npz")[load(artifact["path"]).astype(bool)]}
    obs = {"robot0_eef_pos": robot["eef_xyz_m"], "robot0_eef_quat": robot["eef_quat_xyzw"],
           "robot0_gripper_qpos": robot["finger_positions_m"],
           "robot0_joint_pos": robot["joint_positions_rad"]}
    xml = root / ".venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml"
    adapter = MeasuredSkillAdapter.__new__(MeasuredSkillAdapter)
    adapter.p = SimpleNamespace(env=SimpleNamespace(raw_obs=lambda: obs))
    adapter.geometry = {**panda_geometry(xml), "visual_boxes": gripper_visual_boxes(str(xml))}
    adapter.robot_xml = xml.parent.parent / "robots/panda/robot.xml"
    adapter._instance_cache, adapter._screen_cache, adapter._base_geometry = {}, {}, None
    adapter._self_filtered_capture = None
    adapter.held = adapter.active = adapter.payload_reference = adapter.withdrawal_contact = None
    adapter.instance_boundary_evidence, adapter.committed_grasps, adapter.plans = {}, {}, {}
    adapter.record_public_geometry = False
    entities = {}
    for anchor in row["request"]["anchors"]:
        centre, size = np.asarray(anchor["xyz_m"]), np.asarray(anchor["size_m"])
        entities[anchor["id"]] = Entity(anchor["id"], anchor["label"], tuple(centre),
            tuple(centre-size/2), tuple(centre+size/2), True, step)
    adapter.scene = SimpleNamespace(entities=entities, measurement_clouds_by_view={key: views}, measurement_clouds={})
    adapter.ex = SimpleNamespace(toolkit=SimpleNamespace(_state=SimpleNamespace(latest_step=step, load=frame)))
    adapter._cloud_and_ik()
    reference_file = max((path for path in (directory / "bounded_payload_reference_robot.json").glob("*.json")
                          if int(path.stem) < step), key=lambda path: int(path.stem))
    reference_step = int(reference_file.stem)
    adapter.held = key
    adapter.payload_reference = {
        "target": load(directory / "bounded_payload_reference_target.npz" / f"{reference_step:02d}.npz"),
        "scene": load(directory / "bounded_payload_reference_scene.npz" / f"{reference_step:02d}.npz"),
        "robot": load(reference_file), "capture_step": reference_step}
    queries = []
    if args.save_queries or args.sam_report:
        import base64
        import io

        sam_report = json.loads(args.sam_report.read_text()) if args.sam_report else None
        if sam_report is not None:
            assert sam_report['private_truth_used'] is False

        def save_query(method, *, kwargs, timeout_s):
            assert method == 'sam3.segment'
            raw = base64.b64decode(kwargs['image_base64'])
            camera = next(camera for camera in ('agentview', 'wrist')
                if raw == (directory/(camera+'_high.png')/(f'{step:02d}.png')).read_bytes())
            queries.append({'camera': camera, 'point': kwargs['point'],
                'image': str(directory/(camera+'_high.png')/(f'{step:02d}.png')),
                'image_sha256': hashlib.sha256(raw).hexdigest()})
            if sam_report is None:
                return {'found': False, 'reason': 'CPU_query_registration_only'}
            result = next(r for r in sam_report['results'] if r['camera'] == camera)
            assert kwargs['point'] == result['query']['point']
            if not result['found']:
                return {'found': False, 'reason': result['reason']}
            raw_mask = Path(result['mask']).read_bytes()
            assert hashlib.sha256(raw_mask).hexdigest() == result['sha256']
            with np.load(io.BytesIO(raw_mask)) as archive:
                mask = archive['mask']
            encoded = io.BytesIO()
            Image.fromarray(mask.astype('uint8')*255).save(encoded, format='PNG')
            return {'found': True, 'mask_png_base64': base64.b64encode(encoded.getvalue()).decode(),
                'mask_shape': list(mask.shape), 'score': result['score']}
        adapter.scene.rpc = SimpleNamespace(call=save_query)
        adapter.scene.calls = 0
        adapter.ex.toolkit._state.load_bytes = lambda name: (
            directory/name/(f'{step:02d}'+Path(name).suffix)).read_bytes()
    instance = adapter._instance_pixels(key)
    if args.screen_routes:
        adapter.config = MotionConfig()
        adapter.target_cache = {}
        held_screen = adapter._cloud_and_ik(key, contact=True)
    instance_output = (args.output.with_suffix(".npz") if args.output else
        root/"coordination/bounded_skills_20261016/reports"/(job+"_saved_instance_CPU_20261018.npz"))
    np.savez_compressed(instance_output, points=instance)
    tree = cKDTree(instance)
    scene_tree = cKDTree(adapter._base_geometry[0])
    candidates = []
    for diagnostic in row["candidate_screen_diagnostics"]:
        if diagnostic.get("skill") not in {"carry_to", "nudge", "align"}:
            continue
        groups = diagnostic.get("public_scene_collision_points", {})
        points = [point for values in groups.values() for point in values]
        if not points and diagnostic.get("obstacle_point") is not None:
            points = [diagnostic["obstacle_point"]]
        if not points:
            continue
        distances = tree.query(np.asarray(points))[0]
        scene_distances = scene_tree.query(np.asarray(points))[0]
        candidates.append({"candidate_id": diagnostic.get("candidate_id"), "skill": diagnostic["skill"],
            "parameters": diagnostic["parameters"], "old_reason": diagnostic.get("reason"),
            "old_blockers": len(points), "now_instance_members": int((distances <= 1e-6).sum()),
            "now_in_self_filtered_scene": int((scene_distances <= 1e-6).sum()),
            "nearest_current_scene_m": scene_distances.tolist(),
            "nearest_current_member_m": distances.tolist(), "points_m": points})
        if args.screen_routes:
            evidence = held_screen([diagnostic['at']])
            candidates[-1]['old_rejected_pose_screen'] = evidence
            if diagnostic['skill'] == 'nudge':
                route = adapter._route('nudge', diagnostic['parameters'])
                _, _, _, evidence = SmoothMotion(adapter.p, held_screen, adapter.config).prepare(route)
                candidates[-1]['nudge_route_screen'] = evidence
    points = np.unique([point for candidate in candidates for point in candidate['points_m']], axis=0)
    pixels = []
    for camera, artifact in row['perception_evidence'][key]['sam_mask_files'].items():
        world = frame(camera+'_world_high.npz')
        mask = load(artifact['path']).astype(bool)
        for point in points:
            distances = np.linalg.norm(world-point, axis=2)
            y, x = np.unravel_index(np.argmin(distances), distances.shape)
            if distances[y, x] > 1e-6:
                continue
            pixels.append({'camera': camera, 'xy': [int(x), int(y)], 'xyz_m': point.tolist(),
                'raw_sam_member': bool(mask[y, x]),
                'stationary_scene_distance_m': float(cKDTree(adapter.payload_reference['scene']).query(point)[0]),
                'current_member_distance_m': float(tree.query(point)[0])})
    reports.append({"job": job, "index": index, "anchor_id": key, "capture_step": step,
        "reference_step": reference_step, "instance_points": len(instance),
        "prefix_sha256": hashlib.sha256(b"\n".join(prefix[:index+1])).hexdigest(),
        "candidate_blockers": candidates, "blocker_pixels": pixels, "queries": queries,
        "membership_evidence": adapter.instance_boundary_evidence[key]})
report = {"scope": "CPU saved-sensor membership diagnostic; not a physical or complete route replay",
    "source": str(args.source), "source_sha256": hashlib.sha256((args.source / "robots/libero/bounded_skills.py").read_bytes()).hexdigest(),
    "private_truth_used": False, "new_segmentation_queries": 0, "controls": 0, "training": False,
    "limitation": "No live SAM service or new point prompt; this measures only support in saved public captures.",
    "sam_report": ({'path': str(args.sam_report),
        'sha256': hashlib.sha256(args.sam_report.read_bytes()).hexdigest()} if args.sam_report else None),
    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "cases": reports}
if args.compare_spatial_candidate:
    report['spatial_comparison'] = spatial_comparison
    report['candidate_payload_sha256'] = hashlib.sha256(args.compare_spatial_candidate.read_bytes()).hexdigest()
if args.registration_diagnostics:
    report['registration_diagnostics'] = registration_diagnostics
if args.candidate_registration:
    report['candidate_registration_sha256'] = hashlib.sha256(args.candidate_registration.read_bytes()).hexdigest()
if args.candidate_skills:
    report['candidate_skills_sha256'] = hashlib.sha256(args.candidate_skills.read_bytes()).hexdigest()
if args.screen_routes:
    report['scope'] = 'CPU saved-public-sensor membership, rejected-pose and nudge reference-route screens; zero controls'
    report['limitation'] += ' Route screens use the saved measured robot at rest; no live feedback execution is reproduced.'
output = args.output or root / "coordination/bounded_skills_20261016/reports/bowl_saved_membership_CPU_20261018.json"
output.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({"output": str(output), "cases": [
    {**{key: case[key] for key in ("job", "index", "anchor_id", "instance_points", "blocker_pixels", "queries")},
     "blocked_candidates": len(case['candidate_blockers'])}
    for case in reports]}))
