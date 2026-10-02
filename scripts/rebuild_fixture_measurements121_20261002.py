# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Rebuild parts from declared episode RGB-D files; never infer missing frames."""

import argparse
import functools
import hashlib
import json
import random
from pathlib import Path

import numpy as np

from robots.libero.v5_fixture_parts import above_work_surface, fixture_parts, fixture_points
from robots.libero.v5_state import Entity, entity_record
from scripts.rerender_v5_format118_20261002 import entity, robot_and_axes


@functools.lru_cache(maxsize=4096)
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--trace',type=Path,help='One explicitly declared trace for a bounded development reproduction')
    a=p.parse_args()
    m=json.loads(a.manifest.read_text())
    rd=m['original_target_registry']
    assert sha(rd['path'])==rd['sha256']
    registry=json.loads(Path(rd['path']).read_text())
    configs={str(Path(e['runtime_config_path']).parent):e for e in registry['episodes']}
    a.output.mkdir(parents=True,exist_ok=False)
    inputs=[]
    counts={}
    def count(name):counts[name]=counts.get(name,0)+1
    destination=a.output/'measurements.jsonl'
    with destination.open('x') as output:
        for descriptor in m['runtime_logs']:
            trace_path=Path(descriptor['path'])
            if a.trace and trace_path != a.trace:
                continue
            assert sha(trace_path)==descriptor['sha256']
            config=configs.get(str(trace_path.parent))
            if config is None:
                count('missing_declared_episode_config');continue
            cp=Path(config['runtime_config_path'])
            assert sha(cp)==config['runtime_config_sha256']
            cfg=json.loads(cp.read_text())
            # Canonical EnvState filename, derived only for the declared episode.
            state_path=trace_path.parent/'states.json'
            if not state_path.exists():
                count('missing_states_manifest');continue
            states=json.loads(state_path.read_text())
            states_by_step={x['step_idx']:x for x in states['steps']}
            inputs.extend([{'path':str(state_path),'sha256':sha(state_path)},descriptor])
            events=[json.loads(x) for x in trace_path.read_text().splitlines()]
            used={e['id'] for event in events for field in ('measurements','post_measurements')
                  for e in event.get(field,[]) or []}
            pool=[f'e{i}' for i in range(1,129) if f'e{i}' not in used]
            random.Random(cfg['seed']).shuffle(pool)
            bindings={}
            clouds={}
            crops={}
            support=[e['lower'][2] for e in events[0]['measurements'] if e.get('visible',True)
                     and e['name'] not in ('cabinet','microwave','stove','drawer','rack','basket','caddy')
                     and not e['name'].startswith('area ')]
            support_z=float(np.median(support)) if support else None
            for index,event in enumerate(events,1):
                _,_,axes=robot_and_axes(event['request']['context'])
                front=axes[1] if axes else (0,-1,0)
                for stage,field in [('decision','measurements'),('receipt','post_measurements')]:
                    raw=event.get(field)
                    if raw is None:continue
                    updated=[entity(e) for e in raw if not e.get('part_of')]
                    additions=[];evidence=[];missing=[]
                    for parent in list(updated):
                        if parent.name not in ('cabinet','microwave','stove') or not parent.visible:
                            continue
                        if not above_work_surface(parent,support_z):
                            updated.remove(parent)
                            evidence.append({'parent_id':parent.id,'rejected':'below_measured_work_surface',
                                             'original_measurement':entity_record(parent),'support_z':support_z})
                            count('background_fixture_removed');continue
                        # Legacy records only identify the camera unambiguously at init.
                        # New runtime records carry explicit point-cloud descriptors.
                        live=event.get(('post_' if stage=='receipt' else '')+'fixture_measurement_evidence',{}).get(parent.id)
                        if live:
                            assert sha(live['path'])==live['sha256']
                            with np.load(live['path']) as archive:cloud=archive['array']
                            evidence.append(live)
                        elif parent.source_step==0:
                            initial=states_by_step.get(0,{})
                            name='agentview_world_high.npz'
                            if name not in initial.get('artifacts',[]):
                                missing.append({'parent_id':parent.id,'reason':'initial_world_not_declared'});continue
                            path=trace_path.parent/name/'00.npz'
                            if not path.exists():
                                missing.append({'parent_id':parent.id,'reason':'declared_initial_world_missing'});continue
                            if str(path) not in clouds:
                                with np.load(path) as archive:clouds[str(path)]=archive['array']
                                inputs.append({'path':str(path),'sha256':sha(path)})
                            crop_key=(str(path),parent.lower,parent.upper)
                            if crop_key not in crops:
                                crops[crop_key]=fixture_points(clouds[str(path)],parent)
                            cloud=crops[crop_key]
                            evidence.append({'parent_id':parent.id,'camera':'agentview','source_step':0,
                                             'path':str(path),'sha256':sha(path),
                                             'point_selection':'segmented_bounds_rgbd/1'})
                        else:
                            missing.append({'parent_id':parent.id,'source_step':parent.source_step,
                                            'reason':'legacy_camera_not_explicit'});continue
                        for part in fixture_parts(parent,cloud,front):
                            key=(parent.id,part['name'])
                            if key not in bindings:
                                if not pool:raise ValueError('neutral ID pool exhausted')
                                bindings[key]=pool.pop()
                            additions.append(Entity(bindings[key],**part,part_of=parent.id,
                                                    source_step=parent.source_step))
                    updated.extend(additions)
                    robot = event.get(('post_' if stage=='receipt' else '')+'robot_measurement')
                    robot_source = 'explicit_runtime_proprioception'
                    if robot is None:
                        step = max((e.source_step for e in updated),default=0)
                        measured_state = states_by_step.get(step,{}).get('state',{})
                        robot = {'eef_xyz':measured_state.get('robot0_eef_pos')}
                        robot_source = 'recorded_proprioception_at_latest_entity_frame'
                    count('records');counts['parts_added']=counts.get('parts_added',0)+len(additions)
                    counts['missing_parent_frames']=counts.get('missing_parent_frames',0)+len(missing)
                    output.write(json.dumps({'source_file':str(trace_path),'source_line':index,'stage':stage,
                                             'entities':[entity_record(e) for e in updated],
                                             'robot_measurement':robot,'robot_source':robot_source,
                                             'evidence':evidence,'missing':missing},ensure_ascii=False)+'\n')
            print(json.dumps({'processed_trace':str(trace_path),'counts':counts}),flush=True)
    report={'input_manifest':str(a.manifest),'input_manifest_sha256':sha(a.manifest),
            'files':[{'path':str(destination),'sha256':sha(destination)}],
            'counts':counts,'inputs':inputs,'PRO_inputs_used':False,
            'coordinates_source':'recorded RGB-D backprojection; no simulator object poses',
            'scope':'legacy initial frames and explicitly recorded live fixture clouds only',
            'script_sha256':sha(__file__)}
    (a.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'counts':counts,'manifest_sha256':sha(a.output/'manifest.json')}))


if __name__=='__main__':main()
