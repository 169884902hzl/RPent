# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Label saved microwave states after public decisions; execute no controls."""
# ruff: noqa: E402 -- pin the immutable source and disable GPU before imports
import argparse
import hashlib
import json
import os
import pickle
import sys
from pathlib import Path

os.environ.update(CUDA_VISIBLE_DEVICES='', LIBERO_TYPE='standard', OPENBLAS_NUM_THREADS='1')
root = Path('/public/home/sunyihan/rpent_libero_eval')
parser = argparse.ArgumentParser()
parser.add_argument('--tag', default='chunk_v3_panel_normal2_20261018')
parser.add_argument('--job', default='9018_120')
args = parser.parse_args()
base = root/'coordination/bounded_skills_20261016'
receipt = json.loads((base/'reports'/f'{args.tag}_full_submission.json').read_text())
source = Path(receipt['snapshot'])
sys.path.insert(0, str(source))

import numpy as np
from libero.libero.envs.env_wrapper import ControlEnv

from robots.libero.v5_branch_state import restore_actuators
from robots.libero.v5_reset_seed import attach_reset_seed

case = json.loads(Path(receipt['manifest']['path']).read_text())['cases'][int(args.job.split('_')[1])]
directory = root/'results/bounded_skills/feasibility_20261017'/('job'+args.job)
env = ControlEnv(bddl_file_name=case['bddl']['path'], use_camera_obs=False,
    has_renderer=False, has_offscreen_renderer=False, camera_names=[], ignore_done=True, horizon=10015)
attach_reset_seed(env)
env.seed(0)
env.reset()
records = []
terminal_records = []
try:
    for arm in sorted(directory.glob('*oracle*')):
        choices = arm/'choices.jsonl'
        raw_choices = choices.read_bytes()
        rows = [json.loads(line) for line in raw_choices.splitlines()]
        for row in rows:
            if row.get('event') == 'no_remaining_public_option':
                terminal_records.append({'arm': arm.name, 'record': row})
                continue
            reference = row['private_pre_execution_snapshot']
            raw = Path(reference['path']).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == reference['sha256']
            saved = pickle.loads(raw)
            env.set_init_state(saved['sim_state'])
            restore_actuators(env, saved['actuator_state'])
            residual = float(np.max(np.abs(env.env.sim.get_state().flatten()-saved['sim_state'])))
            assert residual < 1e-8
            joints = {name: np.asarray(env.env.sim.data.get_joint_qpos(name)).tolist()
                for name in env.env.sim.model.joint_names if 'microwave' in name}
            normal = next((item['plan'].get('surface_measurement', {}).get('normal_xyz')
                for item in row['candidate_screen_diagnostics']
                if item.get('stage') == 'fixture_contact_plan' and item.get('anchor_id') == 'e114'), None)
            records.append({'arm': arm.name, 'index': row['index'],
                'sim_steps_before': row['sim_steps_before'], 'snapshot': reference,
                'choices_sha256': hashlib.sha256(raw_choices).hexdigest(),
                'restore_max_error': residual, 'private_joint_qpos': joints,
                'private_task_success': bool(env.env._check_success()),
                'public_normal': normal,
                'public_receipts': [{key: receipt[key] for key in ('skill', 'outcome', 'stop_reason', 'steps_used')}
                    for receipt in row['receipts']]})
finally:
    env.close()
output = base/'reports'/f'microwave{args.job.split("_")[0]}_private_progress_CPU_20261018.json'
output.write_text(json.dumps({'scope': 'private posthoc labels only; no runtime inputs or controls',
    'source': str(source), 'case': case, 'rows': records, 'terminal_records': terminal_records, 'gpu_used': False,
    'controls': 0, 'training': False, 'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, indent=2)+'\n')
print(json.dumps({'output': str(output), 'records': [{key: row[key] for key in
    ('arm', 'index', 'private_joint_qpos', 'private_task_success', 'public_normal')} for row in records]}))
