"""Replay saved public controls to compare cached sensors and rendered geometry.

This original-task diagnostic reads only robot sensor fields from a forced
observation refresh. It neither selects actions from private geometry nor
changes the model-visible adapter.
"""
from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path

import numpy as np

from scripts.probe_bounded_motion import original_session, write

PUBLIC_SENSORS = ('robot0_eef_pos', 'robot0_eef_quat', 'robot0_joint_pos', 'robot0_gripper_qpos')


def sensors(raw):
    return {key: np.asarray(raw[key]).tolist() for key in PUBLIC_SENSORS}


def run(choices, output):
    row = json.loads(Path(choices).read_text().splitlines()[0])
    result = row['execution_details'][0]['execution']
    controls = result['preparation']['trace']+result['trace']
    if len(controls) != result['preparation']['steps_used']+len(result['trace']):
        raise ValueError('preparation controls are incomplete; exact replay is not possible')
    facade, primitives = original_session('libero_spatial', 0, 1, 10000)
    output = Path(output)
    output.mkdir(exist_ok=False, parents=True)
    try:
        worker = facade._env.env.workers[0]
        write(output/'worker_api.json', {'signature': str(inspect.signature(worker.env_call)),
            'source': inspect.getsource(type(worker).env_call)})
        for row in controls:
            primitives._step_env(np.asarray(row['action']))
        cached = sensors(primitives.env.raw_obs())
        rgb, depth = primitives.env.render_camera('agentview', height=1024, width=1024, depth=True)
        np.savez_compressed(output/'render_depth.npz', depth)
        from PIL import Image
        Image.fromarray(np.asarray(rgb)[::-1]).save(output/'render.png')
        refreshed_raw = worker.env_call('_get_observations', kwargs={'force_update': True})
        refreshed = sensors(refreshed_raw)
        write(output/'comparison.json', {
            'status': 'physical_replay', 'controls': len(controls),
            'expected_recorded': result['trace'][-1]['after'], 'cached': cached, 'refreshed': refreshed,
            'difference': {key: (np.asarray(refreshed[key])-cached[key]).tolist() for key in PUBLIC_SENSORS},
            'source': 'public_robot_proprioception_only', 'training': False})
    finally:
        facade.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--choices', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    run(args.choices, args.output)


if __name__ == '__main__':
    main()
