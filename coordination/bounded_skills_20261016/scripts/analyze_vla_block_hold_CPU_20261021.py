"""Test existing RGB-D tracking on recorded VLA block motion; never step physics."""
import argparse
import hashlib
import json
import pickle
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

def main():
    import cv2
    cv2.setNumThreads(1)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--blocks', type=Path, required=True)
    parser.add_argument('--public-probe', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source.resolve(strict=True)))
    from robots.libero.bounded_mask_tracking import track_mask
    frames = pickle.loads(args.blocks.read_bytes())
    probe = pickle.loads(args.public_probe.read_bytes())
    robot = probe['robot']
    payload = (probe['payload']@Rotation.from_quat(robot['eef_quat_xyzw']).as_matrix().T
               + robot['eef_xyz_m'])
    # A probe capture, before any proposed verification motion, must match
    # one recorded block frame exactly in proprioception. Do not bind a
    # target measured after a continuation back to an older policy context.
    matches = [frame for frame in frames if np.allclose(
        frame['robot']['eef_xyz_m'], robot['eef_xyz_m'], rtol=0, atol=1e-8)
        and np.allclose(frame['robot']['eef_quat_xyzw'], robot['eef_quat_xyzw'], rtol=0, atol=1e-8)
        and np.allclose(frame['robot']['finger_positions_m'], robot['finger_positions_m'], rtol=0, atol=1e-8)]
    if not matches:
        raise ValueError('no same-pose public block for the measured probe target')
    final = matches[0]
    rows = []
    for index, earlier in enumerate(frames):
        hand_delta = (np.asarray(earlier['robot']['eef_xyz_m'])
                      - final['robot']['eef_xyz_m'])
        if np.linalg.norm(hand_delta) < .005:
            continue
        for camera, current in final['views'].items():
            before = earlier['views'][camera]
            world = current['world']
            valid = np.isfinite(world).all(axis=2) & (np.abs(world).sum(axis=2) > 1e-6)
            mask = np.zeros(valid.shape, bool)
            mask[valid] = cKDTree(payload).query(world[valid],
                distance_upper_bound=np.nextafter(.003, np.inf))[0] <= .003
            tracked, evidence = track_mask(current['rgb'], before['rgb'],
                world, before['world'], mask)
            residual = (float(np.linalg.norm(np.asarray(evidence['translation_m'])-hand_delta))
                        if tracked is not None else None)
            rows.append({'earlier_index': index, 'camera': camera,
                'earlier_sim_step': earlier['sim_step'], 'final_sim_step': final['sim_step'],
                'earlier_opening_m': earlier['robot']['gripper_opening_m'],
                'hand_displacement_m': float(np.linalg.norm(hand_delta)),
                'initial_target_mask_pixels': int(mask.sum()), 'tracking': evidence,
                'relative_displacement_m': residual,
                'existing_coupling_threshold_passed': residual is not None and residual <= .015})
    result = {'scope': 'offline measurement diagnostic; not a runtime success label or physical replay',
        'source': str(args.source.resolve()),
        'blocks': str(args.blocks), 'blocks_sha256': hashlib.sha256(args.blocks.read_bytes()).hexdigest(),
        'probe': str(args.public_probe), 'probe_sha256': hashlib.sha256(args.public_probe.read_bytes()).hexdigest(),
        'frame_count': len(frames), 'rise_m': probe['rise_m'], 'rows': rows,
        'physics_steps': 0, 'rpc_calls': 0, 'runtime_rule_changed': False}
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'frame_count': len(frames), 'rows': len(rows),
        'tracking_accepted': sum(r['tracking']['accepted'] for r in rows),
        'coupling_passed': sum(r['existing_coupling_threshold_passed'] for r in rows)}))


if __name__ == '__main__':
    main()
