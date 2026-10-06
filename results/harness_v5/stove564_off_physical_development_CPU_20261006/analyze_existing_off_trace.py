"""Original fixed on/off trace audit; private endpoints only score completed runs."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    root,output=args.root,args.output
    output.mkdir(parents=True,exist_ok=True)
    scoring=json.loads((root/'results/harness_v5/stove563_completed_CPU_20261006/labels80_scoring_table.json').read_text())['records']
    labels={(r['case'],r['phase'],r['stage']):r for r in scoring}
    geometry=json.loads((root/'results/harness_v5/stove563_completed_CPU_20261006/public50_geometry.json').read_text())['records']
    original=json.loads((root/'results/harness_v5/stove555_fixed_prefix_CPU_20261006/stove_control_sampling10.json').read_text())
    run=root/'results/harness_v5/stove555_measurement10_original_20261006/probe_job4210'
    inputs=[];rows=[]
    for index,case in enumerate(original['cases']):
        episode=root/'results/harness_v5/stove555_measurement10_original_20261006/probe_job4210'/f'part{index%4}'/case['name']
        for phase in ('on','off'):
            p=episode/phase/'phase.json';data=p.read_bytes()
            inputs.append({'path':str(p),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
            record=json.loads(data);attempt=record['first_attempt'];motions=attempt['motion_evidence']
            chunks=[m for m in motions if m['name']=='vla_act_chunk']
            positions=np.asarray([m['final_eef_pos'] for m in chunks],float)
            openings=np.asarray([m['gripper_opening'] for m in chunks],float)
            actions=np.asarray([action for m in chunks for action in m['actions']],float)
            before,pre,post=[labels[(case['name'],phase,stage)] for stage in ('before_contact','pre_recovery','post_recovery')]
            probes=[r for r in geometry if r['case']==case['name'] and r['phase']=='on' and r['stage']=='post_recovery'
                    and len(r['profiles'].get('64',[]))==1 and r['profiles']['64'][0]['directed_angle_measured']]
            closest=[]
            for public in probes:
                contact=np.asarray(public['profiles']['64'][0]['lever']['upper_patch_centre_xyz_m'])
                distance=np.linalg.norm(positions-contact,axis=-1)
                closest.append({'public_candidate_frame':public['frame'],'public_candidate_contact_xyz':contact.tolist(),
                                'min_eef_distance_m':float(distance.min()),'closest_chunk':int(distance.argmin()+1),
                                'endpoint_semantics_qualified':False})
            row={'case':case['name'],'phase':phase,'prompt':attempt['prompt'],'chunk_count':len(chunks),
                 'chunks_instruction_counts':dict(Counter(m['instruction'] for m in chunks)),
                 'actions_executed':sum(m['executed_action_count'] for m in chunks),
                 'scope':attempt['chunk_completion_scope'], 'private_before_q_rad':before['q_rad'],
                 'private_pre_recovery_q_rad':pre['q_rad'],'private_post_recovery_q_rad':post['q_rad'],
                 'true_before':{'on':before['true_on'],'off':before['true_off']},
                 'true_after':{'on':post['true_on'],'off':post['true_off']},
                 'q_contact_change_rad':pre['q_rad']-before['q_rad'],
                 'q_recovery_change_rad':post['q_rad']-pre['q_rad'],
                 'per_chunk_private_stove_joint_records':sum('joint_qpos' in m or 'stove_joint' in m for m in chunks),
                 'public_eef_trace':{'first_xyz':positions[0].tolist(),'last_xyz':positions[-1].tolist(),
                                     'xyz_range_m':np.ptp(positions,axis=0).tolist(),
                                     'last20_xyz_range_m':np.ptp(positions[-20:],axis=0).tolist(),
                                     'last20_max_chunk_displacement_m':float(np.linalg.norm(np.diff(positions[-20:],axis=0),axis=-1).max()),
                                     'gripper_opening_min_m':float(openings.min()),'gripper_opening_max_m':float(openings.max()),
                                     'actions_last100_translation_abs_mean':np.abs(actions[-100:,:3]).mean(axis=0).tolist(),
                                     'actions_last100_rotation_abs_mean':np.abs(actions[-100:,3:6]).mean(axis=0).tolist()},
                 'distance_to_public_candidate_only':closest,
                 'private_label_refs':[before['label'],pre['label'],post['label']],
                 'motion_trace_scope':'public action/eef trace; no simulated object coordinates used',
                 'classification':'completed_fixed_budget_still_on' if phase=='off' and post['true_on'] else 'fixed_budget_record'}
            rows.append(row)
    off=[r for r in rows if r['phase']=='off']
    summary={'original_cases':10,'on_off_fixed_attempts':20,
             'all_attempts_full160x5':all(r['chunk_count']==160 and r['actions_executed']==800 for r in rows),
             'off_true_off':sum(r['true_after']['off'] for r in off),'off_true_on':sum(r['true_after']['on'] for r in off),
             'off_contact_q_delta_rad_range':[min(r['q_contact_change_rad'] for r in off),max(r['q_contact_change_rad'] for r in off)],
             'off_recovery_q_delta_rad_max_abs':max(abs(r['q_recovery_change_rad']) for r in off),
             'per_chunk_private_stove_joint_records':sum(r['per_chunk_private_stove_joint_records'] for r in rows),
             'root_cause_supported':'Off physically failed despite complete budgets and correct literal prompts; lacks chunk-level stove joint/contact labels to distinguish late reversal from stall',
             'not_supported':'Cannot attribute failure to verification or assert per-chunk contact dynamics from absent private joint traces',
             'runtime_changed':False,'new_simulator_or_GPU_started':False,'private_truth_runtime_injection':False}
    (output/'existing4210_off_trace_report.json').write_text(json.dumps({'summary':summary,'records':rows},indent=2)+'\n')
    (output/'existing4210_off_trace_input_manifest.json').write_text(json.dumps({'files':inputs},indent=2)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':main()
