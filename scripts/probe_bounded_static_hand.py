"""Compare static-robot rendering with a recorded public RGB-D capture.

Only the robot description, public finger/EEF sensors and camera calibration
are used to render the hand. No simulation object identities or poses enter
this diagnostic.
"""
from __future__ import annotations

import argparse
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from scripts.probe_bounded_motion import write


def run(xml, choices, states, metadata, world, output, alignment=None):
    import mujoco

    row = json.loads(Path(choices).read_text().splitlines()[0])
    execution = row['execution_details'][0]['execution']
    robot = execution['trace'][-1]['after']
    records = json.loads(Path(states).read_text())['steps']
    fingers = records[execution['payload_reference_capture_step']+1]['state']['robot0_gripper_qpos']
    if alignment:
        fresh = json.loads(Path(alignment).read_text())['refreshed']
        robot = {**robot, 'eef_xyz_m': fresh['robot0_eef_pos'],
            'eef_quat_xyzw': fresh['robot0_eef_quat'], 'joint_positions_rad': fresh['robot0_joint_pos']}
        fingers = fresh['robot0_gripper_qpos']
    meta = json.loads(Path(metadata).read_text())
    with np.load(world) as stored:
        measured = stored[stored.files[0]]
    height, width = measured.shape[:2]
    root = ET.parse(xml).getroot()
    xml = Path(xml).resolve()
    for mesh in root.findall('asset/mesh'):
        mesh.set('file', str(xml.parent/mesh.get('file')))
    ET.SubElement(root, 'visual')
    ET.SubElement(root.find('visual'), 'global', offwidth=str(width), offheight=str(height))
    body = root.find(".//body[@name='right_gripper']")
    site_rotation = Rotation.from_quat(robot['eef_quat_xyzw'])*Rotation.from_euler('z', -math.pi/2)
    offset = np.array([0., 0., .097])
    body.set('pos', ' '.join(map(str, np.asarray(robot['eef_xyz_m'])-site_rotation.apply(offset))))
    body.set('quat', ' '.join(map(str, site_rotation.as_quat()[[3, 0, 1, 2]])))
    c2w = np.asarray(meta['extrinsic_cam2world'])
    camera_rotation = Rotation.from_matrix(c2w[:3, :3]@np.diag([1., -1., -1.]))
    ET.SubElement(root.find('worldbody'), 'camera', name='measured',
        pos=' '.join(map(str, c2w[:3, 3])),
        quat=' '.join(map(str, camera_rotation.as_quat()[[3, 0, 1, 2]])),
        fovy=str(math.degrees(2*math.atan(meta['height']/(2*meta['intrinsic_K'][1][1])))))
    model = mujoco.MjModel.from_xml_string(ET.tostring(root, encoding='unicode'))
    data = mujoco.MjData(model)
    data.qpos[:] = fingers
    mujoco.mj_forward(model, data)
    option = mujoco.MjvOption()
    option.geomgroup[:] = 0
    option.geomgroup[1] = 1
    option.sitegroup[:] = 0  # Match the task renderer's disabled debug sites.
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    with mujoco.Renderer(model, height=height, width=width) as renderer:
        renderer.update_scene(data, camera='measured', scene_option=option)
        from PIL import Image
        Image.fromarray(renderer.render()).save(output/'robot.png')
        renderer.enable_depth_rendering()
        robot_depth = renderer.render()
    np.savez_compressed(output/'robot_depth.npz', robot_depth)
    k = np.asarray(meta['intrinsic_K'])*np.array([[width/meta['width']]*3,
        [height/meta['height']]*3, [1.]*3])
    hits = execution['handoff']['screen']['public_scene_collision_points']
    reports = []
    from scipy.spatial import cKDTree
    tree = cKDTree(measured.reshape(-1, 3))
    for point in np.unique(np.concatenate([v for v in hits.values() if v]), axis=0):
        distance, index = tree.query(point)
        y, x = np.unravel_index(index, (height, width))
        measured_depth = ((point-c2w[:3, 3])@c2w[:3, :3])[2]
        reports.append({'xyz_m': point.tolist(), 'pixel': [int(y), int(x)],
            'nearest_measured_distance_m': float(distance), 'measured_depth_m': float(measured_depth),
            'robot_depth_m': float(robot_depth[y, x]),
            'depth_difference_m': float(robot_depth[y, x]-measured_depth)})
    write(output/'report.json', {'source': 'static_robot_geometry_public_sensors_camera_calibration',
        'private_scene_coordinates_used': False, 'robot': robot, 'finger_qpos': fingers,
        'intrinsics': k, 'points': reports})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('xml', 'choices', 'states', 'metadata', 'world', 'output'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--alignment')
    args = parser.parse_args()
    run(**vars(args))


if __name__ == '__main__':
    main()
