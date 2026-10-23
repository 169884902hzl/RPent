"""Recover missing retained policy endpoints by replaying their actual controls."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pickle
import sys


def ref(path):
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.mkdir(exist_ok=False)
    os.environ.update(LIBERO_TYPE='pro',LIBERO_CONFIG_PATH='/public/home/sunyihan/rpent_libero_eval/runtime_config')
    sys.path.insert(0,str(args.source))
    spec=importlib.util.spec_from_file_location('first_action_hooks',args.source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py')
    hooks=importlib.util.module_from_spec(spec);spec.loader.exec_module(hooks);hooks.bootstrap_source('d2');hooks.install_d2_restore_compatibility()
    from robots.libero.bounded_hybrid_diagnostic import d2_session,snapshot_digest
    from robots.libero.bounded_motion import public_control
    import numpy as np
    plan=json.loads(args.manifest.read_text())
    for index,job in enumerate(plan['jobs']):
        prior=Path(plan['first_outputs'])/f'closed_{index:03d}.json'
        if prior.exists():continue
        output=args.output/f'case{index:03d}';output.mkdir()
        facade,primitives=d2_session(job['case']['episode'],plan['sim_steps'])
        try:
            saved=pickle.loads(Path(job['initial_snapshot']['path']).read_bytes());observed=facade.restore(saved['physics'])
            facade._native_success_events=copy.deepcopy(saved.get('private_native_success_events',[]))
            primitives.env.last_obs=observed;primitives.env.terminated=primitives.env.truncated=False;primitives.set_obs(observed)
            assert snapshot_digest(facade.snapshot())==snapshot_digest(saved['physics'])
            path=Path(job['retained_attempts']['path']);assert ref(path)==job['retained_attempts']
            first=json.loads(path.open().readline());controls=[*first['trace'],*first['handoff'].get('trace',[])]
            assert len(controls)==first['actual_sim_steps']
            max_error=0.
            for row in controls:
                before,after=public_control(primitives,np.asarray(row['action']))
                for name in ('eef_xyz_m','eef_quat_xyzw','finger_positions_m','joint_positions_rad'):
                    max_error=max(max_error,float(np.max(np.abs(np.asarray(after[name])-row['after'][name]))))
            physics=facade.snapshot();actual=snapshot_digest(physics)
            endpoint=output/'private_attempt0.pkl'
            endpoint.write_bytes(pickle.dumps({'physics':physics,'private_native_success_events':copy.deepcopy(facade._native_success_events),
                'client_stop_flags':{'terminated':primitives.env.terminated,'truncated':primitives.env.truncated},
                'gripper_command':float(controls[-1]['action'][6]),'model_visible':False,'training':False},protocol=5))
            result={'case':job['case'],'attempt_endpoint':ref(endpoint),'expected_first_endpoint_sha256':job['expected_first_endpoint_sha256'],
                'actual_endpoint_physics_sha256':actual,'retained_endpoint_matches':actual==job['expected_first_endpoint_sha256'],
                'sim_steps':len(controls),'max_public_trace_error':max_error,'policy_seed':job['policy_seed'],
                'origin':'exact retained pi0.5 controls including recorded handoff; no new decision or policy inference',
                'new_policy_calls':0,'training':False,'evaluation_only':True,'retained_attempts':job['retained_attempts']}
            (output/'summary.json').write_text(json.dumps(result,indent=2))
            if not result['retained_endpoint_matches']:raise RuntimeError('retained action sequence failed exact physical endpoint recovery')
            (args.output/f'closed_{index:03d}.json').write_text(json.dumps(ref(output/'summary.json')))
            print(json.dumps({'index':index,'case':job['case']['name'],'exact_endpoint':True,'max_public_trace_error':max_error}),flush=True)
        finally:facade.close()


if __name__=='__main__':main()
