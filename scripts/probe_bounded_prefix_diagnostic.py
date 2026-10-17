"""Replay complete saved controls with private contact/joint diagnostics.

Original-scene development only. Diagnostic contacts never select actions or
enter the bounded request. Missing controls fail before creating a simulator.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from robots.libero.bounded_motion import measured_robot
from scripts.probe_bounded_motion import LocalRPC, original_session, write


def prefix_controls(rows, through):
    selected = rows[:through+1]
    if through < 0 or len(selected) != through+1:
        raise ValueError('requested prefix row does not exist')
    controls = []
    for row in selected:
        recorded = []
        for detail in row.get('execution_details', []):
            execution = detail['execution']
            recorded.extend(execution.get('preparation', {}).get('trace', []))
            recorded.extend(execution.get('trace', []))
        count = row['sim_steps_after']-row['sim_steps_before']
        if len(recorded) != count:
            raise ValueError(f"incomplete controls at row {row['index']}: {len(recorded)} != {count}")
        controls.extend({'choice_index': row['index'], **sample} for sample in recorded)
    return controls


def run(choices, suite, task, seed, through, output, render_private_geoms=False,
        compare_depth_sampling=False):
    rows = [json.loads(line) for line in Path(choices).read_text().splitlines()]
    controls = prefix_controls(rows, through)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    facade, primitives = original_session(suite, task, seed, 10000)
    try:
        rpc = LocalRPC(facade)
        with (output/'private_contacts.jsonl').open('w') as ledger:
            for index, sample in enumerate(controls):
                before = measured_robot(primitives)
                primitives._step_env(np.asarray(sample['action']))
                after = measured_robot(primitives)
                diagnostic = rpc.call('diagnostic.motion')
                ledger.write(json.dumps({'control': index, 'choice_index': sample['choice_index'],
                    'action': sample['action'], 'before': before, 'after': after,
                    'recorded_after': sample.get('after'), 'private': diagnostic})+'\n')
        final = measured_robot(primitives)
        if render_private_geoms or compare_depth_sampling:
            for name, camera in (('agentview', 'agentview'), ('wrist', 'robot0_eye_in_hand')):
                evidence = facade._env.env.workers[0].env_call(
                    'v5_pixel_geometry_diagnostic', args=[camera, 1024, 1024, compare_depth_sampling], target='self')
                segmentation = evidence.pop('segmentation')
                np.savez_compressed(output/(name+'_private_geometry.npz'), segmentation)
                for key in list(evidence):
                    if key.endswith(('_rgb', '_depth_buffer')):
                        np.savez_compressed(output/(name+'_'+key+'.npz'), evidence.pop(key))
                write(output/(name+'_private_geometry.json'), evidence)
        expected = controls[-1]['after'] if controls else None
        write(output/'summary.json', {'status': 'physical_prefix_replay',
            'episode': {'suite': suite, 'task': task, 'seed': seed},
            'choices': str(Path(choices).resolve()), 'through': through,
            'controls': len(controls), 'final': final, 'expected': expected,
            'position_replay_error_m': float(np.linalg.norm(np.asarray(final['eef_xyz_m'])-expected['eef_xyz_m'])) if expected else None,
            'source': 'simulation_diagnostic_only', 'training': False})
    finally:
        facade.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--choices', required=True)
    parser.add_argument('--suite', required=True,
        choices=('libero_spatial', 'libero_object', 'libero_goal', 'libero_10', 'libero_90'))
    parser.add_argument('--task', type=int, required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--through', type=int, required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--render-private-geoms', action='store_true')
    parser.add_argument('--compare-depth-sampling', action='store_true')
    run(**vars(parser.parse_args()))


if __name__ == '__main__':
    main()
