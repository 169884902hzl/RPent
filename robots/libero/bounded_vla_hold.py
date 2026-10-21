"""Measure held-object co-motion from RGB-D at completed VLA action blocks."""
from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree

from robots.libero.bounded_mask_tracking import track_mask


def capture_public_block(primitives):
    """Copy native camera sensors, calibration and jaw/EEF proprioception only."""
    from robots.libero.tools import _metric_depth, _world_from_depth

    raw = primitives.env.raw_obs()
    views = {}
    for view, camera in (('agentview', 'agentview'), ('wrist', 'robot0_eye_in_hand')):
        if raw.get(camera+'_image') is None or raw.get(camera+'_depth') is None:
            continue
        rgb = np.asarray(raw[camera+'_image'])[::-1].copy()
        metadata = primitives.env.get_camera_meta(
            camera_name=camera, height=rgb.shape[0], width=rgb.shape[1])
        depth = _metric_depth(raw[camera+'_depth'], metadata)[::-1]
        views[view] = {'rgb': rgb, 'world': _world_from_depth(depth, metadata).astype(np.float32),
                       'metadata': metadata}
    if not views:
        return None
    return {'views': views, 'sim_step': primitives.env.execution_budget()['used_sim_steps'],
        'robot': {'eef_xyz_m': np.asarray(raw['robot0_eef_pos'], float).tolist(),
            'eef_quat_xyzw': np.asarray(raw['robot0_eef_quat'], float).tolist(),
            'finger_positions_m': np.asarray(raw['robot0_gripper_qpos'], float).tolist(),
            'gripper_opening_m': float(np.abs(raw['robot0_gripper_qpos']).sum())}}


def measured_block_hold(frames, current, target, holding_aperture):
    """Track the measured final instance back to an earlier closed-jaw frame.

    This uses movement already executed by the VLA. It neither proposes a
    new motion nor changes collision ownership. Missing/weak tracking leaves
    the existing hold check unmeasured. Aperture, 5 mm observed hand motion
    and the existing 15 mm relative-displacement test remain necessary.
    """
    if current is None or len(target) < 40:
        return None, None
    tree = cKDTree(target)
    masks = {}
    for camera, view in current['views'].items():
        world = view['world']
        valid = np.isfinite(world).all(axis=2) & (np.abs(world).sum(axis=2) > 1e-6)
        mask = np.zeros(valid.shape, bool)
        mask[valid] = tree.query(world[valid],
            distance_upper_bound=np.nextafter(.003, np.inf))[0] <= .003
        masks[camera] = mask
    for earlier in reversed(frames):
        if not holding_aperture(earlier['robot']['gripper_opening_m'])[0]:
            continue
        hand_delta = np.asarray(earlier['robot']['eef_xyz_m'])-current['robot']['eef_xyz_m']
        if np.linalg.norm(hand_delta) < .005:
            continue
        for camera, view in current['views'].items():
            if camera not in earlier['views']:
                continue
            before = earlier['views'][camera]
            tracked, evidence = track_mask(view['rgb'], before['rgb'],
                view['world'], before['world'], masks[camera])
            if tracked is None:
                continue
            residual = float(np.linalg.norm(np.asarray(evidence['translation_m'])-hand_delta))
            if residual > .015:
                continue
            proof = {'source': 'public_rgbd_vla_block_motion', 'camera': camera,
                'earlier_sim_step': earlier['sim_step'], 'current_sim_step': current['sim_step'],
                'hand_displacement_m': float(np.linalg.norm(hand_delta)),
                'relative_displacement_m': residual, 'tracking': evidence,
                'private_truth_used': False, 'new_control_steps': 0}
            pair = {'earlier': earlier, 'current': current,
                    'current_target_mask': masks[camera], 'earlier_tracked_mask': tracked}
            return proof, pair
    return None, None
