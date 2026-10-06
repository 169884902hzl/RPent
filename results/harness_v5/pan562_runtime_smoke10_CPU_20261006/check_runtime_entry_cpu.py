"""Run real SOURCE562 runtime dispatch with CPU stand-ins, never physics."""

import ast
import hashlib
import inspect
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np


source = Path('/public/home/sunyihan/rpent_libero_eval/source_v5_pan562_20261006')
sys.path.insert(0, str(source))
from robots.libero import v5_pan_grasp
from robots.libero.v5_runtime import V5Executor
from robots.libero.v5_state import Entity

out = Path(__file__).resolve().parent / 'preparation'
manifest = json.loads((out / 'pan562_runtime_direct_same10_selection.json').read_text())
condition = next(iter(manifest['conditions'].values()))
flags = {k: v for k, v in condition['overrides'].items() if k in inspect.signature(V5Executor).parameters}
shared_code = (source / 'robots/libero/v5_pan_grasp.py').read_text()
tree = ast.parse(shared_code)
coupled_distances = [n.value.value for n in ast.walk(tree)
                     if isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Subscript)
                     and isinstance(n.target.value, ast.Name) and n.target.value.id == 'translated'
                     and isinstance(n.op, ast.Add) and isinstance(n.value, ast.Constant)]
assert coupled_distances == [.05]
calls, outputs = [], []
old = v5_pan_grasp.rpent_pick_then_independent_handle_measure
for verdict in (True, False, None):
    before = Entity('e1', 'frypan', (0, 0, .95), (-.12, -.08, .9), (.12, .08, 1.), source_step=0)
    raw = {'robot0_eef_quat': [0., 0., 0., 1.]}
    p = SimpleNamespace(_last_obs_eef_pos=np.array([0., 0., 1.2]), _last_obs_gripper=.04,
                        env=SimpleNamespace(raw_obs=lambda: raw))
    executor = V5Executor(SimpleNamespace(primitives=p), SimpleNamespace(entities={'e1': before}), **flags)
    def reject(*a, **kw):
        raise AssertionError('Runtime PAN must bypass ProbeExecutor.vla_act and scripted approach')
    executor.vla_act = reject
    executor.stage_grasp = reject
    executor.stage_category_start = reject
    def fake_shared(actual, prompt, budget, obj, **kwargs):
        assert actual is executor and obj is before
        value = {'prompt': prompt, 'contact_max_chunks': budget, 'trial_lift_m': kwargs['trial_lift_m'],
                 'cross_view_handle_v1': kwargs['cross_view_handle_v1'], 'coupled_lift_v1': kwargs['coupled_lift_v1']}
        assert value == {'prompt': 'pick up the frying pan', 'contact_max_chunks': 320,
                         'trial_lift_m': .10, 'cross_view_handle_v1': True, 'coupled_lift_v1': True}
        calls.append(value)
        kwargs['evidence'].update(stable_visual_grasp={'paired_verdict': {'verified': verdict}})
        return {'executed': True, 'chunks': 20, 'grasp_verified': verdict}
    v5_pan_grasp.rpent_pick_then_independent_handle_measure = fake_shared
    receipt = {}
    executor._execute(SimpleNamespace(tool='grasp', object='e1', mode='direct'), receipt, None)
    assert receipt['grasp_profile'] == 'PAN' and receipt['grasp_verified'] is verdict
    assert receipt['contact_prompt'] == 'pick up the frying pan' and receipt['contact_max_chunks'] == 320
    outputs.append({'input_public_verdict': verdict, 'runtime_receipt': receipt,
                    'scope': 'Real runtime dispatch; fake public shared measurement only, no simulator'})
v5_pan_grasp.rpent_pick_then_independent_handle_measure = old
harness = ast.parse((source / 'harness_v5_eval.py').read_text())
forwarded = {kw.arg for n in ast.walk(harness) if isinstance(n, ast.Call) for kw in n.keywords}
assert {'grasp_category_profiles_v1', 'pan_coupled_lift_v1'} <= forwarded
report = {'scope': 'Real source runtime direct PAN entry with CPU stand-ins; no model, physics or qualification',
          'source': str(source), 'entry': 'V5Executor._execute -> execute_category_grasp(PAN) -> execute_pan_coupled_grasp -> shared helper',
          'ProbeExecutor_vla_act_calls': 0, 'scripted_approach_calls': 0,
          'actual_shared_calls': calls, 'coupled_lift_m_from_source_AST': coupled_distances[0],
          'calibration': condition['overrides']['grasp_measurement_calibration'],
          'harness_forwards_profile_flags': True, 'nullable_public_receipts': outputs,
          'source_shared_sha256': hashlib.sha256((source / 'robots/libero/v5_pan_grasp.py').read_bytes()).hexdigest(),
          'producer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'new_model_calls': 0, 'new_physics': 0, 'passed': True}
(out / 'runtime_entry_cpu_report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'passed': True, 'runtime_shared_calls': len(calls), 'probe_vla_override_calls': 0,
                  'contact_max_chunks': 320, 'trial_lift_m': .10, 'coupled_lift_m': .05}))
