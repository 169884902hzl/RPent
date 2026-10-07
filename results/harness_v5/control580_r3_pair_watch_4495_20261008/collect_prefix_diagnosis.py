"""Compare explicit same-state 4335/4495 ledgers; no causal assignment."""

import json
from pathlib import Path
import subprocess


REMOTE = r'''
from pathlib import Path
import hashlib,json,math
root=Path('/public/home/sunyihan/rpent_libero_eval')
inputs=[]
def read(path,kind,pin=None):
    path=Path(path);raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest()
    if pin is not None and pin!=digest:raise ValueError('pinned input changed: '+str(path))
    inputs.append({'path':str(path),'kind':kind,'sha256':digest})
    return raw
def pinned(ref,kind):return json.loads(read(ref['path'],kind,ref['sha256']))
paths={4335:root/'results/harness_v5/stove568_public_red_recovery_original_20261006/probe_job4335/part0/episodes.jsonl',
       4495:root/'results/harness_v5/temporal_control580_original_r3_20261008/probe_job4495/part0/episodes.jsonl'}
episodes={job:json.loads(read(path,'episode_ledger').decode().splitlines()[0]) for job,path in paths.items()}
assert episodes[4335]['case']==episodes[4495]['case']
initial={};off={}
for job,row in episodes.items():
    initial_public=pinned(row['captures']['before_setup']['public_measurements'],'initial_public_measurements')
    initial[job]={'high_views':{},'agentview_policy_image':None}
    for camera,view in initial_public['views'].items():
        initial[job]['high_views'][camera]={}
        for name,ref in view['files'].items():
            read(ref['path'],'initial_'+camera+'_'+name,ref['sha256'])
            initial[job]['high_views'][camera][name]=ref
    # Explicit runtime artifact convention used by this pinned collector.
    policy=Path(row['output_dir'])/'agentview_policy.png/00.png'
    read(policy,'initial_cached_agentview_policy_image')
    initial[job]['agentview_policy_image']=inputs[-1]
    before=pinned(row['captures']['before_off']['public_measurements'],'pre_off_public_measurements')
    off[job]=before.get('public_observation')
comparisons={}
for phase,key in [('on','on_setup'),('off','off_contact')]:
    a=[r for r in episodes[4335][key]['motion_evidence'] if r['name']=='vla_act_chunk']
    b=[r for r in episodes[4495][key]['motion_evidence'] if r['name']=='vla_act_chunk']
    assert len(a)==len(b)==160
    records=[]
    for index in range(3):
        x,y=a[index],b[index]
        flat_x=[v for act in x['actions'] for v in act];flat_y=[v for act in y['actions'] for v in act]
        diffs=[abs(va-vb) for va,vb in zip(flat_x,flat_y)]
        records.append({'chunk_index':index+1,'same_prompt':x['instruction']==y['instruction'],
            '4335':x,'4495':y,'action_mean_absolute_difference':sum(diffs)/len(diffs),
            'action_max_absolute_difference':max(diffs),'same_actions':flat_x==flat_y})
    comparisons[phase]={'chunks_4335':len(a),'chunks_4495':len(b),'controls_per_chunk':5,
        'first_three_chunks':records,'first_action_equal':a[0]['actions'][0]==b[0]['actions'][0]}
directory=Path(episodes[4495]['output_dir'])
rows=[json.loads(line) for line in read(directory/'public_red_chunks.jsonl','4495_off_chunk_ledger').decode().splitlines()]
tail=[{k:row[k] for k in ('chunk_index','actual_controls','cumulative_contact_controls','robot_before','robot_after','eef_delta_xyz_m')}
      for row in rows[-10:]]
for row in tail:
    row['eef_displacement_m']=math.sqrt(sum(x*x for x in row['eef_delta_xyz_m']))
code={}
for name,path,spans in [
 ('noise_sampler',root/'.venv/lib/python3.10/site-packages/openpi/models_pytorch/pi0_pytorch.py',[(160,172)]),
 ('pi05_eval_sampling',root/'.venv/lib/python3.10/site-packages/rlinf/models/embodiment/openpi/openpi_action_model.py',[(535,580),(636,651),(682,690),(708,717)]),
 ('runtime_capture',root/'source_v5_stove555_20261006/robots/libero/v5_runtime.py',[(105,155)]),
 ('4335_phase_producer',root/'results/harness_v5/stove568_public_stop_selection_CPU_20261006/probe_public_red_recovery.py',[(77,97)]),
 ('4495_phase_producer',root/'results/harness_v5/temporal_control580_capture_CPU_20261007/r3/capture_control_sequence.py',[(235,285)])]:
    lines=read(path,'sampling_source_evidence').decode().splitlines()
    if name=='runtime_capture':
        start=next(index+1 for index,line in enumerate(lines) if line.strip().startswith('def capture('))
        spans=[(start,start+28)]
    code[name]={'path':str(path),'sha256':inputs[-1]['sha256'],
        'excerpts':[{'start_line':start,'end_line':end,'text':'\n'.join(lines[start-1:end])} for start,end in spans]}
rgb_equal={camera:initial[4335]['high_views'][camera]['rgb']['sha256']==initial[4495]['high_views'][camera]['rgb']['sha256']
           for camera in ('agentview','wrist')}
print(json.dumps({'schema':'control580_4335_4495_prefix_diagnosis/1','case':episodes[4495]['case'],
    'initial':initial,'initial_high_rgb_equal':rgb_equal,
    'initial_agentview_policy_image_equal':initial[4335]['agentview_policy_image']['sha256']==initial[4495]['agentview_policy_image']['sha256'],
    'pre_off_public_observation':off,'phase_action_comparisons':comparisons,'4495_last_ten_off_chunks':tail,
    'source_evidence':code,'earliest_observed_divergence':'on_phase_chunk1_action1',
    'initial_model_noise':'sample_noise uses torch.normal; eval still samples initial noise if noise=None',
    'rng_initialization_verified':False,'full_policy_input_bytes_verified':False,
    'capture_causal_effect_isolated':False,'private_truth_controls_actions':False,
    'limits':['Initial native wrist policy input and full model proprioception were not saved for byte comparison.',
        'Sampling code supports stochastic action differences; exact RNG state/seed at inference was not logged.',
        'Earliest observed action divergence precedes off-phase and prevents single-change attribution.',
        'Both off phases execute 160 separate max_chunks=1 calls; neither is one max_chunks=160 call.'],
    'inputs':inputs},indent=2))
'''


if __name__ == '__main__':
    path=Path(__file__).parent/'prefix_diagnosis.json'
    if path.exists():raise SystemExit('Do not overwrite preserved evidence.')
    run=subprocess.run(['timeout','20s','ssh','-o','ConnectTimeout=8','gpu5880-ts','python3','-'],
        input=REMOTE,text=True,capture_output=True,check=True)
    report=json.loads(run.stdout)
    private=json.loads((path.parent/'report.json').read_text())['cases'][0]['private_off_chunk_endpoints']
    by_index={row['chunk']:row for row in private}
    for row in report['4495_last_ten_off_chunks']:
        label=by_index[row['chunk_index']]
        row['private_joint_qpos']=label['private_off_joint_qpos']
        row['private_turn_off_label']=label['turn_off']
    path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'earliest':report['earliest_observed_divergence'],
        'initial_rgb_equal':report['initial_high_rgb_equal'],
        'initial_agentview_policy_image_equal':report['initial_agentview_policy_image_equal']}))
