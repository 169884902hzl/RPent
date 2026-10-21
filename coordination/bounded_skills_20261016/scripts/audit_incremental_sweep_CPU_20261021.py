"""Replay physical-refresh eligibility against saved public control/measurement pairs."""
import argparse
from collections import Counter
from dataclasses import fields
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from robots.libero.bounded_incremental import refresh_names
from robots.libero.v5_state import Entity


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    rows = [json.loads(s) for s in (a.input/'public_incremental_refresh.jsonl').read_text().splitlines()]
    loops = [json.loads(s) for s in (a.input/'loops.jsonl').read_text().splitlines()]
    controls, skills = [], []
    for loop in loops:
        for detail in loop['execution_details']:
            trace = detail.get('execution', {}).get('trace', [])
            if trace:
                candidate = next(c for c in loop['request']['candidates'] if c['id'] == detail['candidate_id'])
                controls.extend({'before': r['before'], 'after': r['after']} for r in trace)
                skills.extend([candidate['skill']]*len(trace))
    assert len(controls) == rows[-1]['used_sim_steps']
    geometry = json.loads((a.input/'public_hand_geometry.json').read_bytes())
    records, previous_step = [], 0
    for i, row in enumerate(rows):
        end = row['used_sim_steps']
        span = controls[previous_step:end]
        entities = {r['id']: Entity(**{**{k: v for k, v in r.items() if k in {f.name for f in fields(Entity)}},
            'source_step': r['capture_step']}) for r in row['before_entities']}
        requested = sorted({e.name for e in entities.values()})
        robot = row['before_robot']
        obs = dict(robot0_eef_pos=robot['eef_xyz_m'], robot0_eef_quat=robot['eef_quat_xyzw'],
            robot0_gripper_qpos=robot['finger_positions_m'], robot0_joint_pos=robot['joint_positions_rad'])
        primitive = SimpleNamespace(env=SimpleNamespace(raw_obs=lambda: obs), _bounded_perception_sweep=span)
        touched = row['touched'] if any(s in {'descend','lower','lift','nudge','guarded_move','set_gripper','release'}
            for s in skills[previous_step:end]) else []
        adapter = SimpleNamespace(p=primitive, ex=SimpleNamespace(toolkit=SimpleNamespace(
            _state=SimpleNamespace(latest_step=row['capture_step']))), geometry=geometry,
            scene=SimpleNamespace(entities=entities, view_axes=((1,0,0),(0,-1,0))),
            held=row['held'], payload_reference=None,
            _incremental_previous_robot=row['previous_robot'], _incremental_touched=touched,
            _incremental_support_changes=set(row['support_changes']) if i>1 else set())
        # The recorder predates complete payload/settling inputs. Do not
        # claim their cache behaviour from an empty-hand reconstruction.
        unsupported = row['held'] is not None or 'release' in skills[previous_step:end]
        actual_names = refresh_names(adapter, requested)
        before = {r['id']: r for r in row['before_entities']}
        after = {r['id']: r for r in row['after_entities']}
        cached = []
        for key, entity in entities.items():
            if entity.name not in actual_names and key in after:
                position = float(np.linalg.norm(np.asarray(after[key]['xyz'])-before[key]['xyz']))
                size = float(np.max(np.abs((np.asarray(after[key]['upper'])-after[key]['lower'])
                    -(np.asarray(before[key]['upper'])-before[key]['lower']))))
                cached.append(dict(anchor_id=key, name=entity.name, position_difference_m=position,
                    max_size_difference_m=size, measurement_change_over_1cm=position>.01 or size>.01))
        old_names = {entities[r['anchor_id']].name for r in row['refresh_reasons']
            if r['changed'] and r['anchor_id'] in entities}
        records.append(dict(capture_step=row['capture_step'], used_sim_steps=end,
            actual_controls=len(span), old_refreshed_names=sorted(old_names),
            new_refreshed_names=actual_names, new_reasons=adapter.incremental_evidence,
            cache_comparisons=cached, evidence_supported=not unsupported,
            unsupported_reason='payload_reference_or_release_settling_not_recorded' if unsupported else None))
        previous_step=end
    supported=[r for r in records if r['evidence_supported']]
    cached=[c for r in supported for c in r['cache_comparisons']]
    report=dict(scope='CPU saved public measurements; no RPC/physics; not N1 speed or true-motion labels',
        inputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in a.input.iterdir() if p.name in {
            'loops.jsonl','public_hand_geometry.json','public_incremental_refresh.jsonl'}},
        captures=len(records), supported_captures=len(supported),
        old_name_measurements=sum(len(r['old_refreshed_names']) for r in supported),
        new_name_measurements=sum(len(r['new_refreshed_names']) for r in supported),
        cache_eligible_anchor_measurements=len(cached),
        cached_measurement_changes_over_1cm=sum(c['measurement_change_over_1cm'] for c in cached),
        max_cached_position_difference_m=max((c['position_difference_m'] for c in cached),default=None),
        max_cached_size_difference_m=max((c['max_size_difference_m'] for c in cached),default=None),
        new_reason_counts=dict(Counter(reason for r in supported for e in r['new_reasons'] for reason in e['reasons'])),
        records=records, training=False, confirmation=False)
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in {'records','inputs'}}))


if __name__=='__main__':
    main()
