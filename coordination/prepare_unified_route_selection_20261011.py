"""Pin paired development plans; measurement replay must pass before submission."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

ROOT=Path('/public/home/sunyihan/rpent_libero_eval')
OUT=ROOT/'results/harness_v5/unified_route_paired_selection_20261011_r2'
PAYLOAD=ROOT/'coordination/unified_route_patch_20261011_r1'
LAUNCH=ROOT/'coordination/run_v5_grasp_measurement_development_20261011.sbatch'
PATCHES=('v5_runtime.py','v5_analytic_grasp.py','v5_grasp_geometry.py','v5_geometric_grasp.py',
         'v5_grasp_route.py','v5_grasp_kinematics.py','v5_grasp_public_tracking.py','v5_grasp_truth.py')


def pin(path):
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def snapshot(parent,name,patches):
    dest=ROOT/name
    shutil.copytree(parent,dest,symlinks=True,ignore=shutil.ignore_patterns(
        '__pycache__','.pytest_cache','.git','.venv','results','coordination','artifacts','assets','docs'))
    for name in patches:
        shutil.copyfile(PAYLOAD/name,dest/'robots/libero'/name)
    files=[{**pin(p),'relative_path':str(p.relative_to(dest))} for p in sorted(dest.rglob('*.py'))]
    identity={'path':str(dest),'parent_source_path':str(parent),'files':files,
              'snapshot_id':dest.name,'purpose':'unified route paired development, not qualification',
              'patch_files':list(patches),'learning_weights_introduced':False}
    (dest/'source_identity_v3r9.json').write_text(json.dumps(identity,indent=2)+'\n')
    archive=dest.with_suffix('.tar')
    with tarfile.open(archive,'x') as stream:
        for child in dest.iterdir():stream.add(child,arcname=child.name)
    identity['archive']={**pin(archive),'archive_complete':True}
    return dest,identity


def main():
    locks=[]
    for filename in ('method_lock_bottle_bowl_cup.json','method_lock_box.json','method_lock_frypan.json'):
        locks.extend(json.loads((ROOT/'coordination/unified_route_inputs_20261011_r1'/filename).read_text())['methods'])
    adapter=ROOT/'coordination/perturb_measurement_adapter_20261011_r4'
    exemplar=json.loads(Path(locks[0]['method_plan']['path']).read_text())
    common_source,common_identity=snapshot(Path(exemplar['source_path']),
        'source_v5_unified_route_selection_20261011_r2',PATCHES)
    common_base=json.loads(Path(exemplar['base_config']['path']).read_text())
    common_base.update(analytic_grasp_v1=True,unified_grasp_route_v1=True,
        geometric_grasp_sampling_v1=True,geometric_pose_screen_v1=True,
        geometric_grasp_active_views_v1=False,grasp_category_profiles_v1=False,
        analytic_side_route_v1=False,analytic_height_envelope_v1=False,
        analytic_contact_precision_v1=True,analytic_geometry_v1=True,
        grasp_public_tracking_v1=True,grasp_independent_views_v1=True,
        grasp_public_coupled_lift_v1=True,grasp_required_coupling_v1=True,
        grasp_public_hold_v1=True,grasp_opposed_pad_window_v1=True,
        dual_view_fusion_v1=True,motion_trace_v1=True,max_chunks=160,
        geometric_gripper_xml=str(ROOT/'.venv/lib/python3.10/site-packages/robosuite/models/assets/grippers/panda_gripper.xml'))
    OUT.mkdir(parents=True,exist_ok=False)
    base=OUT/'common_base_config.json'
    base.write_text(json.dumps(common_base,indent=2)+'\n')
    registrations=[]
    for method in locks:
        category=method['category']
        prior=Path(method['method_plan']['path'])
        if pin(prior)!=method['method_plan']:raise ValueError('locked method plan changed')
        old=json.loads(prior.read_text())
        baseline_source,baseline_identity=snapshot(Path(old['source_path']),
            'source_v5_locked_method_measurement_20261011_r2_'+category,('v5_grasp_truth.py',))
        original_states={c['state_sha256'] for c in old['cases']}
        if len(old['cases'])!=100:raise ValueError('paired selection must contain all original 100 states')
        pairrows=[]
        for arm,source,identity in [('locked',baseline_source,baseline_identity),
                                    ('unified',common_source,common_identity)]:
            plan=copy.deepcopy(old)
            plan.update(source_path=str(source),source_snapshot=identity,adapter_path=str(adapter),
                        cohort='selection',confirmation=False,training_allowed=False,
                        qualification_authorized=False,new_training_rows=0,
                        producer=pin(Path(__file__)),parent_plan=pin(prior),
                        purpose='same original-only selection states, paired locked method vs unified route',
                        closed_confirmation_used=False,resource_rules={'exclude':'node02','nice':500},
                        producer_dependencies=[pin(Path(__file__)),*[pin(adapter/'scripts'/s) for s in (
                            'probe_v5_skill501_original.py','probe_v5_perturb_skill_20261009.py',
                            'v5_perturb_goal_diagnostic.py','v5_perturb_public_reference.py')]])
            if arm=='unified':
                plan['base_config']=pin(base)
                plan['conditions']={'unified_route':{'executor':'current','max_chunks':160,'overrides':{}}}
            else:
                for cond in plan['conditions'].values():cond.setdefault('overrides',{})['motion_trace_v1']=True
            for case in plan['cases']:
                original_name=case['name']
                case.update(name=original_name+'_'+arm+'_routepair',
                    paired_locked_case=original_name,confirmation=False,training_allowed=False)
                if arm=='unified':case['condition']='unified_route'
                pairrows.append({'arm':arm,'case':case['name'],'old_case':original_name,
                                 'state_sha256':case['state_sha256'],'layout_seed':case['layout_seed']})
            if {c['state_sha256'] for c in plan['cases']}!=original_states:
                raise ValueError('paired states changed')
            prep=OUT/category/arm/'preparation';prep.mkdir(parents=True,exist_ok=False)
            path=prep/'selection.json';path.write_text(json.dumps(plan,indent=2)+'\n')
            env=dict(os.environ,PERTURB_SKILL_PLAN=str(path),PERTURB_SKILL_PLAN_SHA=pin(path)['sha256'],
                PERTURB_SKILL_SOURCE=str(source),PERTURB_SKILL_ADAPTER=str(adapter),
                PERTURB_SKILL_OUTPUT=str(prep.parent),PERTURB_SKILL_STARTUP='1',PERTURB_SKILL_CPU_ONLY='1')
            check=subprocess.run(['bash',str(LAUNCH)],cwd='/tmp',env=env,capture_output=True,text=True)
            (prep/'CPU_preflight.log').write_text(check.stdout+check.stderr);check.check_returncode()
            registrations.append({'category':category,'arm':arm,'plan':pin(path),
                                  'physical_submitted':False,'CPU_preflight':'pass'})
        paired=OUT/category/'paired_states.jsonl'
        paired.write_text(''.join(json.dumps(r)+'\n' for r in pairrows))
    manifest={'registered_plans':registrations,'n_states':500,'arms':2,'physical_trials_planned':1000,
              'physical_jobs_submitted':0,'force_limits_changed':False,'policy_chunk_cap':160,
              'new_confirmation_allowed':False,'training_allowed':False,
              'awaiting_measurement_replay':'whole_skill_trace_not_saved=0 and pan16 truth unknown=0',
              'source_snapshot':common_identity,'producer':pin(Path(__file__))}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'plans':len(registrations),'CPU_preflight':'pass','physical_submitted':0}))


if __name__=='__main__':main()
