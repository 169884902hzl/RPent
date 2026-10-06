"""Build explicit stove measurement and fixed-prefix manifests, without physics."""

import hashlib
import json
from pathlib import Path

from scripts.probe_v5_stove521_endpoint import (
    NEARZERO_METHODS, NEARZERO_PREFIXES, NEARZERO_VERSION, validate_manifest, work_items,
)


SOURCE = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parent
REMOTE_ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PARENT = SOURCE / 'results/harness_v5/stove552_control_sampling_CPU_20261006/stove_control_sampling10.json'
SOURCE_FILES = (
    'scripts/probe_v5_stove521_endpoint.py', 'scripts/probe_v5_skill501_original.py',
    'scripts/preflight_v5_stove552.py', 'scripts/v5_probe_preflight.py',
    'scripts/run_v5_stove552_measurement.sbatch', 'robots/libero/v5_stove_probe_env.py',
    'robots/libero/v5_stove_measurement.py', 'robots/libero/v5_fixture_parts.py',
    'robots/libero/v5_runtime.py', 'robots/libero/v5_env_client.py', 'robots/libero/v5_env_server.py',
)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(name, data):
    path = BASE / name
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')
    return {'path': str(path), 'sha256': digest(path)}


sampling = json.loads(PARENT.read_text())
sampling.update(
    parent_measurement_manifest={'path': str(REMOTE_ROOT / PARENT.relative_to(SOURCE)), 'sha256': digest(PARENT)},
    required_source_sha256={name: digest(SOURCE / name) for name in SOURCE_FILES},
    required_probe_sha256=digest(SOURCE / SOURCE_FILES[0]),
    required_stove_module_sha256=digest(SOURCE / 'robots/libero/v5_stove_measurement.py'),
    required_server_sha256=digest(SOURCE / 'robots/libero/v5_stove_probe_env.py'),
    runtime_resources=[{'role': role, 'path': str(REMOTE_ROOT / name)} for role, name in (
        ('interpreter', '.venv/bin/python'), ('libero_config', 'runtime_config/config.yaml'),
        ('pi05_checkpoint', 'assets/pi05'), ('sam3_checkpoint', 'assets/sam3/sam3.pt'))],
    launcher='scripts/run_v5_stove552_measurement.sbatch',
    launcher_status='Runnable explicit manifest; owner must register immutable SOURCE555 and output root before submission',
    final_source_snapshot='SOURCE555 to be registered by root; all required source hashes pinned',
)
validate_manifest(sampling)
nearzero = {**sampling, 'version': NEARZERO_VERSION,
    'purpose': 'Fixed-prefix original off development selection with fresh reset and fixed on preparation',
    'methods': list(NEARZERO_METHODS), 'off_prefix_chunks': list(NEARZERO_PREFIXES),
    'setup_on_chunks': 160, 'fresh_reset_per_cell': True, 'planned_physical_resets': 100,
    'planned_episodes': 100, 'planned_contact_skills': 200, 'shards': 8, 'array': '0-7%8',
    'measurement_stages': ['before_setup', 'after_setup', 'before_off', 'after_prefix', 'post_recovery'],
    'planned_measurement_captures': 500, 'planned_view_captures': 1000,
    'cell_order': 'original init0-9 x public_initial_pose/measured_control_approach x off chunks1/4/16/64/160',
    'setup_policy': 'Every cell runs fixed on160 from a fresh official reset; retain all setup failures and classify only after the complete cell schedule',
    'method_policy': {
        'public_initial_pose': 'Return to reset TCP XYZ and yaw/pitch using proprioception, then fixed original off subtask',
        'measured_control_approach': 'Use existing stage_fixture_handle with current public two-view control measurements; if approach is unmeasured or fails, retain evidence and still run fixed off subtask'},
    'execution': 'Unchanged on160/off160 facade limits; off vla_act receives the fixed smaller prefix, 5 actions/chunk; scope explicitly closed afterward; native success never truncates a prefix; external budget still applies',
    'private_analysis': {
        'on_setup_strata': ['setup_succeeded', 'setup_failed'],
        'bins': [
            {'name': 'nearzero_true_off', 'definition': 'official off=true and -0.005 <= private qpos < 0', 'target_distinct_observations': 20},
            {'name': 'intermediate_dark', 'definition': 'official off=false/on=false and 0 <= private qpos <= 0.05', 'target_distinct_observations': 20},
            {'name': 'other', 'definition': 'Every remaining retained observation'},
            {'name': 'joint_measurement_missing_or_ambiguous', 'definition': 'Private joint label is absent or not a single value'}],
        'timing': 'Computed only after all fixed cell actions and captures; never read by approach, capture schedule, binding or stop',
        'coverage_policy': 'Report actual unique observation coverage and setup strata; no changing thresholds or selecting more prefixes by outcome'},
    'nearzero_driver_implemented': True, 'physical_run_completed': False,
    'training_allowed': False, 'qualification_authorized': False, 'new_training_rows': 0,
}
validate_manifest(nearzero)
assert len(work_items(nearzero)) == 100
references = [save('stove_control_sampling10.json', sampling), save('stove_nearzero_selection100.json', nearzero)]
save('explicit_cell_schedule.json', [{key: case[key] for key in ('name', 'episode', 'method', 'off_prefix_chunks')}
                                    for case in work_items(nearzero)])
print(json.dumps({'manifests': references, 'physical_resets': [10, 100], 'gpu_submitted': False}))
