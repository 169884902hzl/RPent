# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Privately name blocker surfaces by ray casting the unchanged saved state."""

import argparse
import copy
import importlib.util
import json
import os
import pickle
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    public = json.loads(args.public_report.read_bytes())
    source, directory = Path(public['source']), Path(public['directory'])
    os.environ.update(CUDA_VISIBLE_DEVICES='', LIBERO_TYPE='pro',
        OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    sys.path.insert(0, str(source))
    spec = importlib.util.spec_from_file_location('launcher', source/
        'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py')
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    launcher.bootstrap_source('d2')
    import mujoco
    import numpy as np
    from libero.libero.envs.env_wrapper import ControlEnv
    from scipy.spatial.transform import Rotation

    from robots.libero import v5_branch_state

    trial = json.loads((directory/'replay/summary.json').read_bytes())
    assignment = json.loads((directory.parent/'assignment.json').read_bytes())
    physics = pickle.loads(Path(trial['endpoint']['path']).read_bytes())['physics']
    case = assignment['case']
    env = v5_branch_state.attach_branch_state(ControlEnv(bddl_file_name=case['bddl']['path'],
        has_renderer=False, has_offscreen_renderer=False, use_camera_obs=False, camera_names=[],
        ignore_done=True, hard_reset=False, horizon=10015))
    try:
        env.seed(case['episode']['seed'])
        env.reset()
        env.set_init_state(physics['sim_state'])
        actuators = copy.deepcopy(physics['actuator_state'])
        actuators.pop('observation_state', None)
        v5_branch_state.restore_actuators(env, actuators)
        error = float(np.max(np.abs(np.asarray(env.get_sim_state())-physics['sim_state'])))
        if error != 0.:
            raise ValueError('restored physical state differs')
        sim = env.env.sim
        model = sim.model._model
        data = sim.data._data
        metadata = json.loads((directory/'agentview_metadata.json/76.json').read_bytes())
        origin = np.asarray(metadata['extrinsic_cam2world'])[:3, 3]
        robot = json.loads((directory/'first_self_request.json').read_bytes())['robot']
        instance = env.env.robots[0]
        site_id = instance.eef_site_id
        site_id = next(iter(site_id.values())) if isinstance(site_id, dict) else site_id
        robot_error = float(np.linalg.norm(sim.data.site_xpos[site_id]-robot['eef_xyz_m']))
        camera_id = sim.model.camera_name2id('agentview')
        camera_error = float(np.linalg.norm(sim.data.cam_xpos[camera_id]-origin))
        site_rotation = Rotation.from_quat(robot['eef_quat_xyzw']).as_matrix() @ Rotation.from_euler('z', -np.pi/2).as_matrix()
        geometry = pickle.loads(Path(trial['endpoint']['path']).read_bytes())['public_runtime']['adapter']['geometry']
        finger_boxes = geometry['visual_boxes']
        mesh_centres = []
        for box in finger_boxes:
            name = 'gripper0_right_'+box['name']
            gid = sim.model.geom_name2id(name)
            mesh_centres.append({'name': name, 'sim_geom_position_m': sim.data.geom_xpos[gid].tolist(),
                'public_visual_aabb_centre_world_m': (site_rotation @ (
                    (np.asarray(box['lower'])+box['upper'])/2+np.asarray(box['slide_per_half_opening'])*
                    (abs(robot['gripper_opening_m'])/2))+robot['eef_xyz_m']).tolist()})
        rows = []
        for row in public['rows']:
            point = np.asarray(row['point_m'])
            direction = point-origin
            depth = float(np.linalg.norm(direction))
            direction /= depth
            geom = np.full(1, -1, np.int32)
            # Only rendered visual group 1, excluding collision proxies; no labels
            # from these private rays are returned to perception/planning.
            distance = mujoco.mj_ray(model, data, origin, direction,
                np.array([0, 1, 0, 0, 0, 0], np.uint8), 1, -1, geom)
            gid = int(geom[0])
            rows.append({'public_point_m': point.tolist(), 'public_range_m': depth,
                'private_ray_distance_m': distance, 'ray_range_residual_m': distance-depth,
                'private_geom_id': gid,
                'private_geom_name': sim.model.geom_id2name(gid) if gid >= 0 else None,
                'private_body_name': sim.model.body_id2name(int(sim.model.geom_bodyid[gid])) if gid >= 0 else None})
        args.output.write_text(json.dumps({'source': str(source), 'directory': str(directory),
            'physical_state_max_error': error, 'rows': rows, 'physics_steps': 0,
            'robot_eef_position_error_m': robot_error, 'camera_origin_error_m': camera_error,
            'mesh_centres': mesh_centres,
            'gpu_used': False, 'training': False, 'model_visible': False,
            'scope': 'private diagnostic labels only; runtime still uses public RGB-D and robot geometry'}, indent=2))
        print(json.dumps({'rows': len(rows), 'output': str(args.output)}))
    finally:
        env.close()


if __name__ == '__main__':
    main()
