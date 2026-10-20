"""Private development route forks; collision bypass is confined to this probe."""
import argparse
import copy
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pickle
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor


def write(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,default=lambda x:x.tolist() if hasattr(x,'tolist') else str(x))


def checked(ref):
    path=Path(ref['path']).resolve(strict=True)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=ref['sha256']:
        raise ValueError('registered input changed: '+str(path))
    return path


def changed_contacts(initial,current,held_names):
    """Identify new/deeper robot or payload scene contact, retaining raw truth."""
    def key(a,b):return tuple(sorted((a,b),key=lambda name:'' if name is None else name))
    baseline={key(c['geom1'],c['geom2']):c['distance_m'] for c in initial}
    result=[]
    def robot(name):return bool(name and name.startswith(('robot0_','gripper0_')))
    def payload(name):return bool(name and any(name==obj or name.startswith(obj+'_') for obj in held_names))
    for contact in current:
        a,b=contact['geom1'],contact['geom2'];pair=key(a,b)
        if not(robot(a) or robot(b) or payload(a) or payload(b)):continue
        if (robot(a) and payload(b)) or (robot(b) and payload(a)):continue
        distance=contact['distance_m']
        if distance<=0 and (pair not in baseline or distance<baseline[pair]-1e-6):
            result.append(contact)
    return result


def restore_legacy_public_frames(toolkit,reference,robot):
    """Restore real recorded frame IDs and bytes, never constructor frame0."""
    import numpy as np
    from rpent.session.base import StepRecord
    prefix=json.loads(checked(reference['prefix']).read_bytes())
    capture=reference['capture_step']
    if prefix['capture_step']!=capture:raise ValueError('registered legacy capture changed')
    records=prefix['records']
    if [r['step_idx'] for r in records]!=list(range(capture+1)):
        raise ValueError('recorded legacy frame prefix is incomplete')
    state=records[-1]['state']
    q=np.array(state['robot0_eef_quat']);current=np.array(robot['eef_quat_xyzw'])
    if (np.linalg.norm(np.array(state['robot0_eef_pos'])-robot['eef_xyz_m'])>1e-8
            or min(np.linalg.norm(q-current),np.linalg.norm(q+current))>1e-8
            or abs(np.abs(state['robot0_gripper_qpos']).sum()-robot['gripper_opening_m'])>1e-8):
        raise ValueError('recorded public frame does not match restored proprioception')
    store=toolkit._state
    store._output_dir=store._output_dir.parent/'legacy_public_capture'
    store.reset()
    store._steps=[StepRecord(**{**r,'artifacts':set(r['artifacts'])}) for r in records]
    for artifact in reference['artifacts']:
        source=checked(artifact);destination=store._artifact_file(artifact['name'],capture)
        destination.parent.mkdir(exist_ok=True,parents=True);shutil.copyfile(source,destination)
    store._write_manifest()
    return {'source':'verified_recorded_public_frames','capture_step':capture,
        'prefix':reference['prefix'],'copied_artifacts':len(reference['artifacts']),
        'public_pose_match':True,'constructor_frame_used':False}


def verify_fresh_capture(toolkit,robot,constructor_step):
    """Require a newly captured dual view at the restored public robot pose."""
    import numpy as np
    store=toolkit._state;record=store.latest_record()
    if record is None or record.step_idx<=constructor_step:
        raise ValueError('fresh public capture still uses constructor frame')
    state=record.state;q=np.asarray(state['robot0_eef_quat']);current=np.asarray(robot['eef_quat_xyzw'])
    errors={'position_m':float(np.linalg.norm(np.asarray(state['robot0_eef_pos'])-robot['eef_xyz_m'])),
        'quaternion':float(min(np.linalg.norm(q-current),np.linalg.norm(q+current))),
        'opening_m':float(abs(np.abs(state['robot0_gripper_qpos']).sum()-robot['gripper_opening_m']))}
    if any(value>1e-8 for value in errors.values()):
        raise ValueError('fresh public frame does not match restored proprioception: '+str(errors))
    artifacts={}
    for camera in ('agentview','wrist'):
        for suffix in ('_high.png','_world_high.npz'):
            name=camera+suffix;data=store.load_bytes(name)
            artifacts[name]=hashlib.sha256(data).hexdigest()
    return {'source':'fresh_dual_view_after_legacy_physics_restore','capture_step':record.step_idx,
        'constructor_frame_used':False,'public_pose_errors':errors,'artifact_sha256':artifacts}


def saved_runtime(source,row,directory,rpc):
    """Restore ordinary adapter resources; share SAM and omit the VLA model."""
    from contextlib import contextmanager
    @contextmanager
    def opened():
        import robosuite
        from scripts import probe_bounded_hybrid_d2 as probe
        from robots.libero.bounded_hybrid_diagnostic import d2_session
        from scripts.probe_bounded_motion import original_session,LocalRPC
        from robots.libero.toolkit import LiberoToolkit
        from robots.libero.v5_runtime import MeasuredScene
        from robots.libero.bounded_skills import MeasuredSkillAdapter
        from robots.libero.bounded_oracle import BoundedOracle
        from rpent.dashboard.events import NullDashboardEventSink
        from rpent.memory import MemoryManager
        from rpent.robots.components.sam3_client import Sam3Client
        case=row['case'];ep=case['episode']
        if row['domain']=='original':
            facade,p=original_session(ep['suite'],ep['task'],ep['seed'],10000,rgbd_no_msaa_v1=True)
        else:facade,p=d2_session(ep)
        toolkit=None
        try:
            toolkit=LiberoToolkit(runtime_kwargs={'env':p.env,'model':None,'sam3_client':Sam3Client(rpc)},
                dashboard_events=NullDashboardEventSink(),
                memory=MemoryManager(directory/'empty_memory',memory_access='read_only'),
                state_output_dir=directory/'artifacts',artifact_compression_level=1)
            scene=MeasuredScene(toolkit,rpc,ep['seed'],dual_view_fusion_v1=True,
                furniture_parts_v1=True,instruction_queries_v1=True,wrist_recall_v1=True,
                occluded_measurement_cache_v2=True,**probe.BOUNDED_SCENE_FLAGS)
            executor=probe.make_executor(toolkit,scene,case)
            xml=Path(robosuite.__file__).parent/'models/assets/grippers/panda_gripper.xml'
            adapter=MeasuredSkillAdapter(executor,xml,allow_vla=False)
            policy=BoundedOracle(LocalRPC(facade),adapter)
            historical=pickle.loads(checked(row['start_checkpoint']).read_bytes())
            if row.get('public_reconstruction')=='fresh_dual_view':
                from scripts.probe_bounded_hybrid_repair import restore_original_subtask
                runtime=historical['public_runtime'];old=runtime['adapter']
                scene.instruction=executor.instruction=runtime['scene']['instruction']
                scene.vocabulary=set(probe.public_vocabulary(scene.instruction))
                adapter.preparation=copy.deepcopy(old['preparation'])
                adapter.held=old['held'];adapter.payload_reference=copy.deepcopy(old.get('payload_reference'))
                # The existing restoration helper consumes only these
                # already measured public fields; no private goal/position
                # label is added to the reconstructed observation.
                transport={'adapter':SimpleNamespace(scene=SimpleNamespace(entities=runtime['scene']['entities']),
                    p=SimpleNamespace(**runtime['primitive']),held=old['held'],payload_reference=old.get('payload_reference')),
                    'scope':'measured public-state transport only; not an oracle label snapshot'}
                flat=directory/'private_legacy_physics.pkl';flat.write_bytes(pickle.dumps(historical['physics'],protocol=5))
                annotation=directory/'legacy_public_transport.pkl.gz'
                annotation.write_bytes(gzip.compress(pickle.dumps(transport,protocol=5),mtime=0))
                constructor_step=toolkit._state.latest_step
                restored=restore_original_subtask(facade,adapter,policy,
                    {'physics':probe.reference(flat),'annotation':probe.reference(annotation)})
                adapter.gripper_command=old['gripper_command']
                if old['held'] not in scene.entities or not adapter.holding_aperture(adapter.robot()['gripper_opening_m'])[0]:
                    adapter.held=adapter.active=None;adapter.payload_reference=None
                if old.get('active') in scene.entities:adapter.active=old['active']
                adapter._branch_complete_integration_available=restored['historical_complete_integration_available']
                adapter._diagnostic_frame_restore=verify_fresh_capture(toolkit,adapter.robot(),constructor_step)
                adapter._diagnostic_frame_restore['restoration']=restored
                if row['candidate']['skill']=='move_to':adapter.request(k=4)
            else:
                probe.restore_checkpoint(facade,adapter,policy,historical)
                executor.instruction=scene.instruction
                if 'artifact_state' not in historical['public_runtime']:
                    if not row.get('legacy_public_frames'):
                        raise ValueError('legacy checkpoint requires its registered public frames')
                    adapter._diagnostic_frame_restore=restore_legacy_public_frames(
                        toolkit,row['legacy_public_frames'],adapter.robot())
            adapter.record_public_geometry=False
            yield probe,facade,adapter,policy
        finally:
            if toolkit is not None:toolkit.close()
            facade.close()
    return opened()


def worker(a,plan):
    row=plan['jobs'][a.worker]
    os.environ['LIBERO_TYPE']='standard' if row['domain']=='original' else 'pro'
    os.environ['LIBERO_GRASP_DIAGNOSTIC_MODELS']=str(a.output/'private_models')
    helpers=a.source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py'
    spec=importlib.util.spec_from_file_location('zero_fork_hooks',helpers)
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    helper.bootstrap_source('d2');helper.install_d2_restore_compatibility()
    from robots.libero.bounded_motion import SmoothMotion,measured_robot
    from rpent.utils.rpc.http_rpc import HttpRpcClient
    assignment=json.loads((a.output/'assignment.json').read_bytes())
    rpc=HttpRpcClient(assignment['sam3_url'])
    with saved_runtime(a.source,row,a.output,rpc) as (probe,facade,adapter,policy):
        historical_integration=getattr(adapter,'_branch_complete_integration_available',False)
        candidate=row['candidate'];skill=candidate['skill'];parameters=candidate['parameters']
        if skill=='call_vla':
            route=[{'xyz_m':adapter.preparation['eef_xyz_m'],'quat_xyzw':adapter.preparation['eef_quat_xyzw']}]
        elif skill=='move_to':route=adapter._route(skill,parameters)
        elif skill=='observe':
            robot=adapter.robot()
            route=[{'xyz_m':[x+d for x,d in zip(robot['eef_xyz_m'],row['recorded_scan_offset_m'])],
                'quat_xyzw':robot['eef_quat_xyzw']}]
        else:raise ValueError('this probe admits saved preparation/move routes only')
        if not route:raise ValueError('saved route unavailable; do not invent a replacement')
        contact=(adapter.active or (adapter.withdrawal_contact or {}).get('anchor_id')) if skill=='observe' else None
        adapter._cloud_and_ik(parameters.get('anchor_id') if skill=='move_to' else contact,
            contact=contact is not None)
        # Freeze any point-prompt measurement before branching. Both arms
        # consume the same public cloud, rather than repeating segmentation.
        common,ref=probe.save_checkpoint(facade,adapter,policy,a.output/'private_complete_common.pkl')
        arms=[]
        for name in ('checks_on','collision_checks_off'):
            probe.restore_checkpoint(facade,adapter,policy,common)
            initial_sha=probe.snapshot_digest(facade.snapshot())
            if initial_sha!=ref['physics_sha256']:raise ValueError('full fork initial state differs')
            start_truth=facade.grasp_contacts()
            held=[obj for obj,value in start_truth['objects'].items() if value['dual_finger_contact']]
            before_robot=adapter.robot();trajectory=[];new_contacts=[]
            original_step=adapter.p._step_env
            def observed_step(action):
                original_step(action)
                truth=facade.grasp_contacts()
                collisions=changed_contacts(start_truth['contacts'],truth['contacts'],held)
                new_contacts.extend(collisions)
                trajectory.append({'truth':truth,'new_or_deeper_contacts':collisions,'robot':adapter.robot()})
            screen=adapter._cloud_and_ik(parameters.get('anchor_id') if skill=='move_to' else contact,
                contact=contact is not None)
            import numpy as np
            signature=hashlib.sha256()
            for points in (screen.points,screen.target,screen.payload):
                array=np.asarray(points,dtype='<f8');signature.update(str(array.shape).encode());signature.update(array.tobytes())
            public_input_sha=signature.hexdigest()
            if name=='collision_checks_off':
                screen=copy.copy(screen)
                screen.ik=screen.ik.with_measured_robot(measured_robot(adapter.p))
                screen.use_kernel=False;screen.check_arm=False
                screen._geometry_at=lambda pose:{'passed':True,'path_min_clearance_m':.2}
            adapter.p._step_env=observed_step
            started=time.perf_counter()
            try:result=SmoothMotion(adapter.p,screen,adapter.config).run(route,gripper=adapter.gripper_command)
            finally:adapter.p._step_env=original_step
            endpoint=facade.grasp_contacts()
            from scipy.spatial.transform import Rotation
            robot=adapter.robot()
            angular=float((Rotation.from_quat(robot['eef_quat_xyzw'])*Rotation.from_quat(route[-1]['quat_xyzw']).inv()).magnitude())
            reached=(result.get('endpoint_error_m',1.)<=adapter.config.endpoint_tolerance_m
                and angular<=.05 and result['stop_reason']=='endpoint')
            payload={}
            for obj in held:
                relative0=(np.array(start_truth['objects'][obj]['xyz'])-before_robot['eef_xyz_m'])@Rotation.from_quat(before_robot['eef_quat_xyzw']).as_matrix()
                shifts=[float(np.linalg.norm((np.array(t['truth']['objects'][obj]['xyz'])-t['robot']['eef_xyz_m'])
                    @Rotation.from_quat(t['robot']['eef_quat_xyzw']).as_matrix()-relative0)) for t in trajectory]
                payload[obj]={'retained_dual_contact':endpoint['objects'][obj]['dual_finger_contact'],
                    'max_relative_displacement_m':max(shifts,default=0.)}
            payload_ok=all(v['retained_dual_contact'] and v['max_relative_displacement_m']<=.01 for v in payload.values())
            payload_known=adapter.held is None or bool(held)
            physical_collision=bool(new_contacts) if trajectory else None
            safe_completion=(False if new_contacts else payload_ok if reached and payload_known else None) if trajectory else None
            directory=a.output/name;directory.mkdir()
            write(directory/'private_contact_trace.json',{'initial':start_truth,'trace':trajectory,'endpoint':endpoint})
            write(directory/'execution.json',result)
            arms.append({'arm':name,'initial_physics_sha256':initial_sha,'wall_s':time.perf_counter()-started,
                'public_screen_input_sha256':public_input_sha,
                'steps_used':result['steps_used'],'stop_reason':result['stop_reason'],'screen':result.get('screen'),
                'reached':reached,'physical_collision':physical_collision,'safe_route_completion':safe_completion,
                'angular_endpoint_error_rad':angular,'payload':payload,'payload_truth_known':payload_known,
                'new_contact_count':len(new_contacts),'private_contact_trace':str(directory/'private_contact_trace.json')})
        result={'source_commit':plan['source_commit'],'diagnostic_script':plan['script'],
            'registered_action':row,'route':route,'arms':arms,
            'common_state':ref,'status':'physical_result','training':False,'confirmation':False,
            'scope':'route only; preparation does not run pi0.5; old-rejected-action cohort, not general collision false-negative rate',
            'public_frame_restoration':getattr(adapter,'_diagnostic_frame_restore',{'source':'saved_artifact_state'}),
            'historical_complete_integration_available':historical_integration,
            'new_common_complete_integration_available':common['physics'].get('actuator_state',{}).get('integration') is not None,
            'contact_definition':'new pair or penetration deepened >1um; robot/payload versus scene; held-hand contacts exempt; raw samples retained'}
        if len({arm['public_screen_input_sha256'] for arm in arms})!=1:
            raise ValueError('paired public screen inputs differ')
        write(a.output/'summary.json',result)
        if a.startup and not any(arm['steps_used']>0 for arm in arms):raise RuntimeError('startup had no physical controls')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--worker',type=int)
    p.add_argument('--startup',action='store_true');p.add_argument('--preflight',action='store_true')
    p.add_argument('--episode-concurrency',type=int,default=8)
    a=p.parse_args();a.source=a.source.resolve(strict=True);sys.path.insert(0,str(a.source))
    plan=json.loads(a.manifest.resolve(strict=True).read_bytes())
    if plan['training'] or plan['confirmation'] or plan['kind']!='zero_step_collision_forks':
        raise ValueError('development-only private collision fork plan required')
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=plan['script']['sha256']:
        raise ValueError('registered diagnostic script changed')
    if json.loads((a.source/'SOURCE_REVISION.json').read_bytes())['commit']!=plan['source_commit']:
        raise ValueError('registered runtime snapshot changed')
    from scripts.bounded_state_exclusions import check_exclusions
    check_exclusions([row['case'] for row in plan['jobs']],plan['registry'])
    if a.worker is not None:return worker(a,plan)
    checked(plan['sam_entry'])
    for row in plan['jobs']:
        if row['candidate']['skill'] not in {'call_vla','move_to','observe'}:raise ValueError('unsupported replay skill')
        if row['candidate']['skill']=='observe' and (row['candidate']['parameters']['mode']!='wrist_scan'
                or len(row['recorded_scan_offset_m'])!=3):raise ValueError('recorded scan route required')
        for ref in (row['start_checkpoint'],row['choices'],row['case']['bddl'],row['case']['grasp_measurement_calibration']):
            if not Path(ref['path']).is_absolute() or not Path(ref['path']).is_file():raise FileNotFoundError(ref['path'])
    if a.preflight:print(json.dumps({'preflight':'passed','actions':len(plan['jobs'])}));return
    if not 1<=a.episode_concurrency<=8:raise ValueError('episode concurrency must be1..8')
    a.output.mkdir(exist_ok=True,parents=True)
    pending=[]
    for i in range(len(plan['jobs'])):
        summaries=[a.output/f'case{i:03d}'/'summary.json',*a.output.glob(f'case{i:03d}_attempt*/summary.json')]
        if not any(path.exists() for path in summaries):pending.append(i)
    if not pending:return
    def command(index,directory,startup=False):
        cmd=[sys.executable,str(Path(__file__).resolve()),'--source',str(a.source),'--manifest',str(a.manifest),
            '--output',str(directory),'--worker',str(index)]
        if startup:cmd+=['--startup']
        return cmd
    def run(index,assignment):
        directory=a.output/f'case{index:03d}'
        if directory.exists():
            attempt=1
            while (a.output/f'case{index:03d}_attempt{attempt}').exists():attempt+=1
            directory=a.output/f'case{index:03d}_attempt{attempt}'
        directory.mkdir()
        write(directory/'assignment.json',assignment)
        with (directory/'worker.log').open('x') as log:
            result=subprocess.run(command(index,directory),stdout=log,stderr=subprocess.STDOUT)
        print(json.dumps({'index':index,'exit_code':result.returncode,'directory':str(directory)}),flush=True)
        return result.returncode
    hooks=a.source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py'
    spec=importlib.util.spec_from_file_location('zero_fork_service_hooks',hooks)
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    helper.bootstrap_source('d2')
    from scripts.probe_bounded_feasibility import services
    with helper.owned_services(SimpleNamespace(source=a.source,output=a.output,
            sam3_entry=Path(plan['sam_entry']['path'])),services,vla=False) as endpoints:
        assignment={'sam3_url':endpoints['sam3']._base_url}
        startup=a.output/f'startup_{time.time_ns()}';startup.mkdir();write(startup/'assignment.json',assignment)
        with (startup/'worker.log').open('x') as log:subprocess.run(command(plan.get('startup_index',pending[0]),startup,True),stdout=log,stderr=subprocess.STDOUT,check=True)
        with ThreadPoolExecutor(a.episode_concurrency) as pool:codes=list(pool.map(lambda i:run(i,assignment),pending))
    if any(codes):raise RuntimeError('development errors retained; repair and resume')


if __name__=='__main__':main()
