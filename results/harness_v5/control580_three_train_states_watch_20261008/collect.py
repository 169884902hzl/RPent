"""Read three fixed original training states, with pinned public/label files."""

import json
import subprocess
from pathlib import Path


REMOTE = r'''
from pathlib import Path
from collections import Counter
import hashlib,json
root=Path('/public/home/sunyihan/rpent_libero_eval/results/harness_v5')
manifest_path=root/'temporal_control580_capture_CPU_20261007/r2/capture_manifest.json'
manifest=json.loads(manifest_path.read_text());inputs=[];cases=[];frame_rows=[]
def read(path,kind,pin=None):
    path=Path(path);raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if pin is not None and pin!=sha:raise ValueError('pinned file changed: '+str(path))
    inputs.append({'path':str(path),'kind':kind,'sha256':sha})
    return json.loads(raw)
inputs.append({'path':str(manifest_path),'kind':'capture_manifest','sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest()})
for job,part in [(4467,0),(4474,1),(4474,2)]:
    out=root/'temporal_control580_original_r2_20261007'/f'probe_job{job}'/f'part{part}'
    boundary=read(out/'collector_boundary.json','collector_boundary')
    p=out/'episodes.jsonl';raw=p.read_bytes();inputs.append({'path':str(p),'kind':'episodes','sha256':hashlib.sha256(raw).hexdigest()})
    row=json.loads(raw.decode().splitlines()[0]);case=row['case'];phase_labels=[]
    for phase,refs in row['captures'].items():
        labels=read(refs['labels']['path'],'private_phase_labels',refs['labels']['sha256'])
        predicates=labels['requested_predicates']
        phase_labels.append({'phase':phase,'source_step':labels['source_step'],
            'turn_off':predicates['turn_off']['satisfied'],'turn_on':predicates['turn_on']['satisfied']})
    for phase,refs in row['public_sequences'].items():
        sequence=read(refs['public_sequence']['path'],'public_sequence',refs['public_sequence']['sha256'])
        private=read(refs['private_sequence_labels']['path'],'private_sequence_index',refs['private_sequence_labels']['sha256'])
        if len(sequence['frames'])!=len(private['labels']):raise ValueError('unpaired sequence frames and labels')
        for index,(frame,ref) in enumerate(zip(sequence['frames'],private['labels'])):
            labels=read(ref['path'],'private_frame_label',ref['sha256'])
            public=read(frame['public_measurements']['path'],'public_frame_measurement',frame['public_measurements']['sha256'])
            predicates=labels['requested_predicates'];views={}
            for camera,view in frame['views'].items():
                feature=view.get('control_features') or {}
                views[camera]={k:feature.get(k) for k in ('source_step','src','parent','control_pose','directed_lever',
                    'stove_reference','signed_angle_to_reference_deg','endpoint_state','valid_control_candidates',
                    'reason','unmeasured_features','feature_binding')}
                views[camera]['control_pose_measured']=feature.get('control_pose') is not None
                views[camera]['directed_angle_measured']=feature.get('signed_angle_to_reference_deg') is not None
                views[camera]['control_feature_record_present']=bool(feature)
            frame_rows.append({'episode':case['episode'],'phase':phase,'frame_index':index,
                'source_step':frame['source_step'],'coordinate_source':frame.get('coordinate_source'),
                'current_control_resegmented':frame.get('current_control_resegmented'),
                'control_roi_source':frame.get('control_roi_source'),
                'private_object_or_joint_values_in_public':frame.get('private_object_or_joint_values'),
                'arm_withdrawn_claim':frame.get('arm_withdrawn_claim'),'hold_controls_since_previous_frame':frame.get('hold_controls_since_previous_frame'),
                'public_current_shell_count':public.get('current_shell_count'),
                'public_parent_binding':public.get('control_parent_binding'),
                'turn_off_label':predicates['turn_off']['satisfied'],'turn_on_label':predicates['turn_on']['satisfied'],
                'views':views,'public_measurements':frame['public_measurements'],'private_labels':ref})
    chunk_path=Path(row['output_dir'])/'public_red_chunks.jsonl';chunk_raw=chunk_path.read_bytes();chunks=[json.loads(x) for x in chunk_raw.decode().splitlines()]
    inputs.append({'path':str(chunk_path),'kind':'executed_chunk_ledger','sha256':hashlib.sha256(chunk_raw).hexdigest()})
    endpoints=[]
    for chunk in chunks:
        # The pinned producer writes this fixed sibling at capture_one:108.
        label_path=Path(chunk['public_frame']['public_measurements']['path']).parent/'labels.json'
        labels=read(label_path,'private_off_chunk_endpoint_label')
        predicates=labels['requested_predicates']
        endpoints.append({'chunk':chunk['chunk_index'],'after_contact_controls':chunk['cumulative_contact_controls'],
            'turn_off':predicates['turn_off']['satisfied'],'turn_on':predicates['turn_on']['satisfied'],
            'private_off_joint_qpos':predicates['turn_off']['joint_qpos'],'labels_path':str(label_path)})
    positives=[endpoint for endpoint in endpoints if endpoint['turn_off']]
    cases.append({'job':job,'part':part,'episode':case['episode'],'state_sha256':case['state_sha256'],
        'boundary':boundary,'fixed_phase_labels':phase_labels,'off_chunks':len(chunks),
        'each_chunk_executes_five_controls':all(x['actual_controls']==5 for x in chunks),
        'chunk_indices_complete': [x['chunk_index'] for x in chunks]==list(range(1,161)),
        'source_steps_strictly_increase':all(b['source_step']>a['source_step'] for a,b in zip(chunks,chunks[1:])),
        'off_actual_controls':sum(x['actual_controls'] for x in chunks),
        'private_turn_off_true_chunk_endpoints':len(positives),
        'private_turn_on_true_chunk_endpoints':sum(endpoint['turn_on'] for endpoint in endpoints),
        'first_turn_off_true_after_controls':positives[0]['after_contact_controls'] if positives else None,
        'last_turn_off_true_after_controls':positives[-1]['after_contact_controls'] if positives else None,
        'first_private_endpoint':endpoints[0],'last_private_endpoint':endpoints[-1],
        'private_joint_qpos_range':[min(e['private_off_joint_qpos'][0][0] for e in endpoints),max(e['private_off_joint_qpos'][0][0] for e in endpoints)],
        'private_turn_off_per_control_labels_saved':False,'private_off_chunk_endpoints':endpoints,
        'first_off_chunk':{k:chunks[0][k] for k in ('chunk_index','source_step','actual_controls','cumulative_contact_controls')},
        'last_off_chunk':{k:chunks[-1][k] for k in ('chunk_index','source_step','actual_controls','cumulative_contact_controls')}})
views=[v for frame in frame_rows for v in frame['views'].values()]
print(json.dumps({'format':'control580_three_train_states/1','jobs':[4467,4474],
    'original_task_only':True,'model_training_performed':False,'stop_admitted':False,
    'confirmation_registry_complete':manifest['confirmation_registry_complete'],
    'registered_confirmation_overlap':manifest['registered_confirmation_overlap'],
    'execution_source_root':manifest['execution_source_root'],'source_files':manifest['source_files'],
    'summary':{'raw_states':len(cases),'actual_contact_controls':sum(x['boundary']['actual_contact_controls'] for x in cases),
        'off_executed_chunk_rows':sum(x['off_chunks'] for x in cases),'temporal_public_frames':len(frame_rows),
        'public_view_records':len(views),'turn_off_positive_temporal_labels':sum(x['turn_off_label'] for x in frame_rows),
        'private_turn_off_true_chunk_endpoints':sum(x['private_turn_off_true_chunk_endpoints'] for x in cases),
        'private_turn_off_sampled_chunk_endpoints':sum(x['off_chunks'] for x in cases),
        'control_feature_records_present':sum(v['control_feature_record_present'] for v in views),
        'public_view_records_without_control_feature_query':sum(not v['control_feature_record_present'] for v in views),
        'turn_on_positive_temporal_labels':sum(x['turn_on_label'] for x in frame_rows),
        'control_pose_measured_views':sum(v['control_pose_measured'] for v in views),
        'directed_angle_measured_views':sum(v['directed_angle_measured'] for v in views),
        'control_feature_reason_counts':dict(Counter(v['reason'] for v in views)),
        'endpoint_state_counts':dict(Counter(v['endpoint_state'] for v in views)),
        'current_control_resegmented_frame_counts':dict(Counter(str(x['current_control_resegmented']) for x in frame_rows))},
    'interpretation_limits':['Complete physical collection is not successful turn_off or verifier qualification.',
        'Temporal rows from the same raw state are correlated; view/frame counts are availability statistics.',
        'Private turn_off labels were saved after each five-control chunk, not at each individual control.',
        'Feature-null raw frames were intentionally retained without a repeated SAM query; they are not failed query results.',
        'Private predicates are offline labels only, never runtime control inputs.',
        'Registered exclusion overlap zero is not proof of a complete confirmation exclusion registry.'],
    'cases':cases,'temporal_frames':frame_rows,'inputs':inputs},ensure_ascii=False,indent=2))
'''


if __name__ == '__main__':
    path=Path(__file__).parent/'report.json'
    if path.exists():
        raise SystemExit('Do not overwrite preserved evidence.')
    run=subprocess.run(['timeout','20s','ssh','-o','ConnectTimeout=8','gpu5880-ts','python3','-'],
                       input=REMOTE,text=True,capture_output=True,check=True)
    result=json.loads(run.stdout)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result['summary'],ensure_ascii=False))
