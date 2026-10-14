"""One monitoring pass: record failed jobs and release passing startup arrays."""
import datetime,hashlib,json,os,subprocess,fcntl
from pathlib import Path
ROOT=Path('/public/home/sunyihan/rpent_libero_eval');RECEIPT=ROOT/'coordination/registered_grasp_v3r9_monitor_ledger.jsonl'
release_lock=(ROOT/'coordination/registered_grasp_v3r9_release.lock').open('a')
fcntl.flock(release_lock,fcntl.LOCK_EX)
base=ROOT/'results/harness_v5/registered_grasp_v3r9_r2_diagnostic_20261010'
parents=[base/'bowl_analytic',base/'cup_pi05']+list((ROOT/'results/harness_v5/registered_grasp_v3r9_selection_20261010').iterdir())
parents += [ROOT/'results/harness_v5/public_grasp_pose_r6_selection_20261010'/name
            for name in ('bottle_pi05_pose', 'cup_pi05_pose', 'bowl_analytic_reference')]
parents += [ROOT/'results/harness_v5/public_grasp_tracking_r7_selection_20261010'/name
            for name in ('bottle_pi05_stationary', 'cup_pi05_stationary')]
parents += [ROOT/'results/harness_v5/public_grasp_pad_r8_selection_20261010_r3'/name
            for name in ('bottle_analytic', 'bottle_pi05', 'cup_pi05')]
parents += [ROOT/'results/harness_v5/public_grasp_inner_pad_r9_selection_20261010_r1'/name
            for name in ('bottle_analytic', 'bottle_pi05', 'cup_pi05')]
parents += [ROOT/'results/harness_v5/public_grasp_probe_motion_r10_selection_20261010_r1'/'bottle_pi05']
parents += [ROOT/'results/harness_v5/public_grasp_float32_r11_selection_20261010_r2'/name
            for name in ('bottle_analytic', 'bottle_pi05', 'cup_pi05')]
parents += [ROOT/'results/harness_v5/analytic_contact_precision_r12_selection_20261010_r2'/'bottle_analytic']
parents += [ROOT/'results/harness_v5/analytic_contact_precision_bowl_pan_selection_20261010_r1'/name
            for name in ('bowl_analytic', 'pan_analytic')]
parents += [ROOT/'results/harness_v5/analytic_side_route_wired_box_selection_20261010_r1'/'box_analytic_side']
parents += [ROOT/'results/harness_v5/bottle_height_envelope_r14_selection_20261010_r1'/'bottle_analytic']
parents += [ROOT/'results/harness_v5/public_servo_coupling_r16_selection_20261010_r1'/name
            for name in ('bottle_analytic', 'bottle_pi05', 'cup_pi05')]
parents += [ROOT/'results/harness_v5/public_physical_hold_r18_selection_20261010_r1'/name
            for name in ('bottle_analytic', 'bottle_pi05', 'cup_pi05')]
parents += [ROOT/'results/harness_v5/servo_only_fiveclass_selection_20261010_r1'/name
            for name in ('bottle_analytic', 'bowl_analytic', 'box_analytic', 'cup_analytic', 'frypan_analytic')]
parents += [ROOT/'results/harness_v5/geometric_grasp_selection_20261010_r1'/name
            for name in ('box_depth_cleanup', 'cup_identity_guard', 'frypan_connected_handle',
                         'bottle_geometric_sampling', 'bowl_geometric_sampling',
                         'box_geometric_sampling', 'cup_geometric_sampling', 'frypan_geometric_sampling')]
parents += [ROOT/'results/harness_v5/geometric_grasp_selection_20261010_r2'/name
            for name in ('box_depth_cleanup', 'cup_identity_guard', 'frypan_connected_handle',
                         'bottle_geometric_sampling', 'bowl_geometric_sampling',
                         'box_geometric_sampling', 'cup_geometric_sampling', 'frypan_geometric_sampling')]
parents += [ROOT/'results/harness_v5/geometric_grasp_selection_20261010_r3'/name
            for name in ('frypan_connected_handle', 'bottle_geometric_sampling', 'bowl_geometric_sampling',
                         'box_geometric_sampling', 'cup_geometric_sampling', 'frypan_geometric_sampling')]
parents += [ROOT/'results/harness_v5/analytic_failure_phases_selection_20261010_r1'/name
            for name in ('bottle_analytic', 'bowl_analytic', 'box_analytic', 'cup_analytic', 'frypan_analytic')]
parents += [ROOT/'results/harness_v5/geometric_grasp_selection_20261010_r4'/name
            for name in ('bowl_local_opposition', 'box_depth_identity_cleanup')]
parents += [ROOT/'results/harness_v5/geometric_grasp_selection_20261010_r5'/name
            for name in ('bottle_coherent_sampling', 'bowl_coherent_sampling', 'box_coherent_sampling',
                         'cup_coherent_sampling', 'frypan_coherent_sampling')]
parents += [ROOT/'results/harness_v5/geometric_grasp_selection_20261010_r6'/'box_oblique_views_r2']
parents += [ROOT/'results/harness_v5/geometric_grasp_selection_20261010_r7'/name
            for name in ('bottle_coherent_precision', 'bowl_coherent_precision', 'box_coherent_precision',
                         'cup_coherent_precision', 'frypan_coherent_precision')]
parents += [ROOT/'results/harness_v5/geometric_grasp_selection_20261010_r7'/('pi05_' + name + '_reference')
            for name in ('bottle', 'bowl', 'box', 'cup', 'frypan')]
parents += [ROOT/'results/harness_v5/geometric_grasp_selection_20261010_r7'/'bowl_neutral_query']
parents += [ROOT/'results/harness_v5/geometric_grasp_selection_20261010_r7'/(name + '_pad_contact_alignment')
            for name in ('bottle', 'bowl', 'box', 'cup', 'frypan')]
parents += [ROOT/'results/harness_v5/geometric_grasp_selection_20261010_r8'/(name + '_public_pose_screen')
            for name in ('bottle', 'bowl', 'box', 'cup', 'frypan')]
parents += [ROOT/'results/harness_v5/geometric_grasp_selection_20261010_r9'/(name + '_rotation_scale')
            for name in ('bottle', 'bowl', 'box', 'cup', 'frypan')]
parents += [ROOT/'results/harness_v5/geometric_grasp_selection_20261010_r10'/(name + '_mesh_hull')
            for name in ('bottle', 'bowl', 'box', 'cup', 'frypan')]
parents += [ROOT/'results/harness_v5/geometric_grasp_selection_20261010_r11'/'box_identity_exclusion']
parents += [ROOT/'results/harness_v5/geometric_grasp_selection_20261010_r12'/'box_semantic_query']
parents += [ROOT/'results/harness_v5/geometric_grasp_selection_20261010_r13'/'frypan_public_coupling']
parents += [ROOT/'results/harness_v5/geometric_grasp_confirmation_20261010_r1'/name
            for name in ('bottle', 'bowl', 'box', 'cup', 'frypan')]
parents += [ROOT/'results/harness_v5/grasp_confirmation_startup_resume_20261010_r1'/'bowl']
for parent in parents:
 if (parent/'preparation/superseded_submission.json').exists():continue
 submission=parent/'preparation/submission.json'
 if not submission.is_file():continue
 if (parent/'preparation/formal_submission.json').exists():continue
 r=json.loads(submission.read_text());j=r['startup_job'].split(';')[0]
 status=subprocess.run(['sacct','-j',j,'-X','-n','-P','-o','JobID,State,ExitCode'],capture_output=True,text=True,check=True).stdout
 if '|FAILED|' in status or '|CANCELLED|' in status or '|TIMEOUT|' in status:
  print('startup needs repair:',j,status,flush=True);continue
 contract=parent/f'job{j}/part0/startup_contract.json'
 if not contract.exists():print('startup running/pending:',j,flush=True);continue
 c=json.loads(contract.read_text())
 if c['status']!='pass' or c['physical_controls']<=0:raise RuntimeError('invalid physical startup contract')
 rows=[json.loads(l) for l in Path(c['episodes']['path']).open() if l.strip()]
 if not rows or rows[0].get('infrastructure_failure'):raise RuntimeError('startup infrastructure failure')
 dtype_evidence=[]
 if r.get('public_rgbd_storage_dtype') == 'float32':
  import numpy as np
  startup_root=parent/f'job{j}/part0/probe'
  for camera in ('agentview','wrist'):
   candidates=sorted(startup_root.glob(f'*/attempt0/{camera}_world_high.npz/*.npz'))
   if not candidates:raise RuntimeError(f'startup has no actual {camera} world map')
   path=candidates[-1]
   with np.load(path) as archive:
    arrays={key:str(archive[key].dtype) for key in archive.files}
   if not arrays or any(value != 'float32' for value in arrays.values()):
    raise RuntimeError(f'startup world map not FP32: {path} {arrays}')
   dtype_evidence.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                          'array_dtypes':arrays})
 plan=json.loads(Path(r['plan']['path']).read_text())
 remaining=sum(case['name']!=c['case_name'] for case in plan['cases'])
 shards=min(8,remaining)
 if not shards:raise RuntimeError('single-case plans need no formal array; only startup was registered')
 env=dict(os.environ,PERTURB_SKILL_PLAN=r['plan']['path'],PERTURB_SKILL_PLAN_SHA=r['plan']['sha256'],PERTURB_SKILL_SOURCE=plan['source_path'],PERTURB_SKILL_ADAPTER=plan['adapter_path'],PERTURB_SKILL_OUTPUT=str(parent),PERTURB_SKILL_STARTUP='0',PERTURB_SKILL_STARTUP_CONTRACT=str(contract),PERTURB_SKILL_SHARDS=str(shards))
 result=subprocess.run(['sbatch','--parsable','--chdir=/tmp',f'--array=0-{shards-1}%8','--export=ALL',r['launcher']['path']],env=env,capture_output=True,text=True,check=True)
 receipt={**r,'formal_job':result.stdout.strip().split(';')[0],'formal_shards':shards,'remaining_registered_cases':remaining,'startup_contract_path':str(contract),'startup_contract_sha256':hashlib.sha256(contract.read_bytes()).hexdigest(),'physical_controls':c['physical_controls'],'released_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'qualification_allowed':bool(plan.get('confirmation') and plan.get('qualification_authorized'))}
 if dtype_evidence:receipt['actual_public_world_map_dtypes']=dtype_evidence
 (parent/'preparation/formal_submission.json').write_text(json.dumps(receipt,indent=2)+'\n')
 with RECEIPT.open('a') as out:out.write(json.dumps(receipt)+'\n')
 print(json.dumps(receipt),flush=True)
