"""Reproduce the D2 solver-state restore on CPU without cameras or controls from VLA."""
import argparse
import copy
import importlib.util
import json
import os
import pickle
import sys
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--checkpoint',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--index',type=int,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--spawn',action='store_true',help='Exercise the actual RLinf spawned-worker transport')
    args=parser.parse_args()
    os.environ.update(LIBERO_TYPE='pro',CUDA_VISIBLE_DEVICES='')
    sys.path.insert(0,str(args.source))
    spec=importlib.util.spec_from_file_location('shared_launcher',Path(__file__).with_name('shared_gpu_episodes_20261019.py'))
    launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)
    launcher.bootstrap_source('d2')
    import numpy as np
    from libero.libero.envs.env_wrapper import ControlEnv
    from robots.libero import v5_branch_state
    from robots.libero.bounded_hybrid_diagnostic import snapshot_digest

    case=json.loads(args.manifest.read_bytes())['cases'][args.index]
    saved=pickle.loads(args.checkpoint.read_bytes())['physics']
    def factory():
        from robots.libero.v5_branch_state import attach_branch_state
        return attach_branch_state(ControlEnv(bddl_file_name=case['bddl']['path'],has_renderer=False,
            has_offscreen_renderer=False,use_camera_obs=False,camera_names=[],
            ignore_done=True,hard_reset=False,horizon=10015))
    if args.spawn:
        from rlinf.envs.libero.venv import ReconfigureSubprocEnvWorker
        env=ReconfigureSubprocEnvWorker(launcher.d2_spawn_factory(factory))
    else:
        env=factory()
    try:
        if args.spawn:
            env.env_call('seed',args=[case['episode']['seed']],target='self')
            env.reset()
        else:
            env.seed(case['episode']['seed']);env.reset()
        def actuator_state():
            return (env.env_call('v5_actuator_state',target='self') if args.spawn
                else v5_branch_state.actuator_state(env))
        def capture():
            value=copy.deepcopy(saved)
            value['sim_state']=env.get_sim_state()
            value['actuator_state']=actuator_state()
            return value
        def restore():
            env.set_init_state(saved['sim_state'])
            if args.spawn:
                env.env_call('v5_restore_actuators',args=[saved['actuator_state']],target='self')
            else:
                v5_branch_state.restore_actuators(env,saved['actuator_state'])
        restore()
        before=snapshot_digest(capture())
        warmstart_before=actuator_state()['data']['qacc_warmstart'].copy()
        if not args.spawn:launcher.install_d2_restore_compatibility()
        restore()
        after=snapshot_digest(capture())
        action=np.array([.01,-.01,.01,0.,0.,0.,-1.])
        endpoints=[]
        for _ in range(2):
            restore()
            for _ in range(5):
                if args.spawn:env.env_call('step',args=[action],target='self')
                else:env.step(action)
            endpoints.append(snapshot_digest(capture()))
        report={'scope':'same saved BDDL/physics, CPU MuJoCo with cameras disabled; wrapper counters copied',
            'source':str(args.source),'checkpoint':str(args.checkpoint),'case':case['name'],
            'gpu_used':False,'training':False,'expected_digest':snapshot_digest(saved),
            'actual_RLinf_spawn_transport':args.spawn,
            'uncorrected_digest':before if not args.spawn else None,'corrected_digest':after,
            'first_spawned_restore_digest':before if args.spawn else None,
            'changed_warmstart_scalars':int(np.sum(warmstart_before!=saved['actuator_state']['data']['qacc_warmstart'])),
            'exact_physics_controller_rng_restore':after==snapshot_digest(saved),
            'successor_control_steps':5,'successor_digest_twice':endpoints,
            'successor_control_identical':endpoints[0]==endpoints[1],
            'launcher_sha256':launcher.digest(Path(__file__).with_name('shared_gpu_episodes_20261019.py'))}
        args.output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report),flush=True)
        assert report['exact_physics_controller_rng_restore']
        assert report['successor_control_identical']
    finally:
        env.close()


if __name__=='__main__':main()
