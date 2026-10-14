"""Compare public Panda mesh transforms with a robot-only MuJoCo model."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import mujoco
import numpy as np


def pin(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--xml', type=Path, required=True)
    parser.add_argument('--geometry-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('recorded_public_gripper', args.geometry_source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    geometry = module.panda_geometry(args.xml.resolve())
    model = mujoco.MjModel.from_xml_path(str(args.xml.resolve()))
    data = mujoco.MjData(model)
    site = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, 'grip_site')
    names = {'palm': 'hand_collision', 'leftfinger': 'finger1_collision',
        'rightfinger': 'finger2_collision', 'leftfinger_pad': 'finger1_pad_collision',
        'rightfinger_pad': 'finger2_pad_collision'}
    records = []
    for aperture in (0., .02, .04, .06, .08):
        data.qpos[:] = [aperture / 2, -aperture / 2]
        mujoco.mj_forward(model, data)
        for box in geometry['boxes']:
            geom = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, names[box['name']])
            mesh = model.geom_dataid[geom]
            if model.geom_type[geom] == mujoco.mjtGeom.mjGEOM_MESH:
                start, count = model.mesh_vertadr[mesh], model.mesh_vertnum[mesh]
                vertices = model.mesh_vert[start:start + count]
            else:
                size = model.geom_size[geom]
                vertices = np.asarray([(x, y, z) for x in (-size[0], size[0])
                    for y in (-size[1], size[1]) for z in (-size[2], size[2])])
            points = ((vertices @ data.geom_xmat[geom].reshape(3, 3).T + data.geom_xpos[geom]
                       - data.site_xpos[site]) @ data.site_xmat[site].reshape(3, 3))
            slide = np.asarray(box.get('slide_per_half_opening', [0, 0, 0])) * aperture / 2
            error = max(abs(points.min(0) - (np.asarray(box['lower']) + slide)).max(),
                        abs(points.max(0) - (np.asarray(box['upper']) + slide)).max())
            records.append({'aperture_m': aperture, 'part': box['name'], 'maximum_bound_error_m': float(error)})
    args.output.mkdir(parents=True, exist_ok=False)
    records_path = args.output / 'records.json'
    records_path.write_text(json.dumps(records, indent=2) + '\n')
    producer_path = args.output / Path(__file__).name
    producer_path.write_bytes(Path(__file__).read_bytes())
    report = {'source': pin(args.geometry_source), 'robot_geometry': geometry['references'],
        'producer': pin(producer_path), 'records': pin(records_path), 'comparisons': len(records),
        'maximum_bound_error_m': max(r['maximum_bound_error_m'] for r in records),
        'object_scene_loaded': False, 'grasp_success_test': False,
        'limits': ['This checks static robot mesh positions and aperture signs only.',
                   'It does not validate scene perception, collisions along a moving arm, or grasp success.']}
    (args.output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('comparisons', 'maximum_bound_error_m', 'grasp_success_test')}))


if __name__ == '__main__':
    main()
