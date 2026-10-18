"""Private saved-boundary metrology; never supplies a public motion option."""
import hashlib
import json
import os
import pickle
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', LIBERO_TYPE='standard', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
prep = json.loads((base/'reports/chunk_v3_prefix_checks_20261018_preparation.json').read_text())
sys.path.insert(0, prep['snapshot'])
import numpy as np
from libero.libero.envs.env_wrapper import ControlEnv
from robots.libero.v5_branch_state import restore_actuators
from robots.libero.v5_reset_seed import attach_reset_seed

cases = json.loads(Path(prep['manifest']['path']).read_text())['cases']
case = cases[80]
env = ControlEnv(bddl_file_name=case['bddl']['path'], use_camera_obs=False,
    has_renderer=False, has_offscreen_renderer=False, camera_names=[], ignore_done=True, horizon=10015)
attach_reset_seed(env)
env.seed(case['episode']['seed'])
env.reset()
results = []
try:
    for path in sorted((root/'results/bounded_skills/feasibility_20261017/job8843_80').glob('*oracle*/choices.jsonl')):
        rows = [json.loads(line) for line in path.open()]
        samples = []
        for row in rows:
            ref = row.get('private_pre_execution_snapshot')
            if ref is None:
                continue
            raw = Path(ref['path']).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == ref['sha256']
            saved = pickle.loads(raw)
            env.set_init_state(saved['sim_state'])
            restore_actuators(env, saved['actuator_state'])
            error = float(np.max(np.abs(env.env.sim.get_state().flatten()-saved['sim_state'])))
            assert error < 1e-9
            joints = {}
            for i in range(env.env.sim.model.njnt):
                name = env.env.sim.model.joint_id2name(i)
                if name and any(token in name for token in ('cabinet', 'drawer')):
                    joints[name] = np.asarray(env.env.sim.data.get_joint_qpos(name)).tolist()
            candidates = {c['id']: c for c in row['request']['candidates']}
            selected = [candidates[cid] for cid in row.get('decision', {}).get('candidate_ids', [])]
            samples.append(dict(index=row['index'], sim_steps=row.get('sim_steps_before'),
                private_joints=joints, private_native_success=bool(env.env._check_success()),
                source_snapshot=ref, restored_state_max_error=error,
                selected=[{k: c[k] for k in ('skill', 'parameters')} for c in selected]))
        results.append(dict(choices=str(path), choices_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            samples=samples))
finally:
    env.close()
report = dict(scope='private CPU state restoration without renderer or policy actions; not a new rollout or rescore',
    private_truth_used_for_control=False, GPU_used=False, training=False, case=case, arms=results)
output = base/'reports/drawer8843_joint_boundaries_private_CPU_20261018.json'
output.write_text(json.dumps(report, indent=2)+'\n')
for arm in results:
    print(arm['choices'])
    for sample in arm['samples']:
        print(json.dumps({k: sample[k] for k in ('index', 'sim_steps', 'private_joints', 'private_native_success', 'selected')}))
