"""Pre-register 24 deterministic original-layout rawstates without changing goals."""

import hashlib
import json
from pathlib import Path

import numpy as np


ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
OUT = Path(__file__).resolve().parent / 'preparation'
STATES = OUT / 'registered_layout24'


def identity(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')
    return identity(path)


def digest(state):
    return hashlib.sha256(np.asarray(state, dtype='<f8', order='C').tobytes()).hexdigest()


def main():
    import torch
    from libero.libero.envs.env_wrapper import ControlEnv
    from robots.libero.v5_reset_seed import attach_reset_seed

    OUT.mkdir(parents=True, exist_ok=True)
    STATES.mkdir(parents=True, exist_ok=True)
    catalog_path = ROOT / 'results/harness_v5/collection540_capacity_CPU_20261006/preparation/original130_catalog.json'
    catalog = json.loads(catalog_path.read_text())
    task = next(t for t in catalog if t['suite'] == 'libero_90' and t['task'] == 19)
    standard = ROOT / '.venv/lib/python3.10/site-packages/libero/libero'
    assets = {key: identity(standard / directory / 'libero_90' / Path(task[key]['path']).name)
              for key, directory in [('bddl', 'bddl_files'), ('init_file', 'init_files')]}
    for key in assets:
        if assets[key]['sha256'] != task[key]['sha256']:
            raise ValueError('Installed standard original task bytes changed')
    anchors = torch.load(assets['init_file']['path'], weights_only=False)
    offsets = [(x/1000, y/1000) for x in (-20, -12, -4, 4, 12, 20)
               for y in (-15, -5, 5, 15)]
    rule = {
        'authorization': 'User 2026-10-07 explicitly approved24 preregistered original-layout perturbation rawstates in addition to76 official states; original goals and thresholds unchanged; source strata separate; no PRO; no physical-failure reruns.',
        'original_scene': {'suite': 'libero_90', 'task': 19},
        'exact_original_instruction': 'put the moka pot on the stove',
        'unchanged_original_goals': task['oracle_goal_predicates'],
        'bddl': assets['bddl'], 'official_init_file': assets['init_file'],
        'moved_free_joint_object': 'moka_pot_1',
        'anchor_official_indices': list(range(10, 34)),
        'layout_seeds': list(range(2026100700, 2026100724)),
        'grid_order': 'x-major then y-minor; grid index i uses official anchor10+i and layout_seed2026100700+i',
        'dx_m': [-.020, -.012, -.004, .004, .012, .020],
        'dy_m': [-.015, -.005, .005, .015],
        'fixture_reset_seed': 'Unchanged official anchor seed; layout_seed identifies the deterministic grid and does not resample static fixtures',
        'all_other_rawstate_values': 'Preserve every other qpos, all qvel, actuator state and time from the anchor bytes',
        'rawstate_encoding': 'C contiguous little endian float64',
        'success_threshold': .90, 'public_verifier_agreement_threshold': .95,
        'excluded_from_training': True, 'physical_outcome_used_for_generation': False,
        'invalid_state_policy': 'Keep deterministic state and report preparation error; never resample or replace a state based on a rollout result',
        'producer': identity(__file__), 'catalog': identity(catalog_path),
    }
    # Freeze the numerical rule before creating or inspecting a simulator.
    rule_ref = write(OUT / 'layout24_preregistered_rule.json', rule)
    env = attach_reset_seed(ControlEnv(bddl_file_name=assets['bddl']['path'],
        use_camera_obs=False, has_renderer=False, has_offscreen_renderer=False,
        initialization_noise=None, ignore_done=True, hard_reset=True))
    cases, checks, seen = [], [], set()
    excluded = {h for t in catalog for h in t['state_sha256']}
    try:
        for index, (dx, dy) in enumerate(offsets):
            anchor_index = 10+index
            layout_seed = 2026100700+index
            env.seed(anchor_index)
            env.reset()
            anchor = np.asarray(anchors[anchor_index], dtype='<f8', order='C')
            if digest(anchor) != task['state_sha256'][anchor_index]:
                raise ValueError('Official anchor rawstate changed')
            env.set_init_state(anchor)
            joint = env.env.objects_dict['moka_pot_1'].joints[0]
            qpos_address = env.sim.model.get_joint_qpos_addr(joint)
            start, end = qpos_address
            if end-start != 7:
                raise ValueError('Selected original moka is not a seven-value freejoint')
            changed_indices = [int(1+start), int(2+start)]
            state = anchor.copy()
            state[changed_indices] += [dx, dy]
            current_digest = digest(state)
            if current_digest in seen or current_digest in excluded:
                raise ValueError('New layout rawstate overlaps another registered or official state')
            seen.add(current_digest)
            unchanged = np.ones(len(state), dtype=bool)
            unchanged[changed_indices] = False
            if not np.array_equal(state[unchanged], anchor[unchanged]):
                raise ValueError('Layout generation changed another rawstate field')
            env.set_init_state(state)
            restored = np.asarray(env.get_sim_state(), dtype='<f8', order='C')
            if not np.allclose(state, restored, atol=1e-8, rtol=0):
                raise ValueError('Prepared layout cannot be restored exactly')
            initial_done = bool(env.check_success())
            if initial_done:
                raise ValueError('Prepared layout is already an original task success')
            value = {'episode': {'suite': 'libero_90', 'task': 19, 'seed': anchor_index},
                'layout_seed': layout_seed, 'source': 'preregistered_original_layout_perturbation',
                'rule': rule_ref, 'bddl': assets['bddl'], 'official_init_file': assets['init_file'],
                'parent_official_state_sha256': digest(anchor), 'parent_official_init_index': anchor_index,
                'rawstate': state.tolist(), 'state_shape': list(state.shape),
                'state_sha256': current_digest, 'changed_flat_indices': changed_indices,
                'delta_xy_m': [dx, dy], 'instruction': rule['exact_original_instruction'],
                'private_original_goal_predicates': task['oracle_goal_predicates'],
                'task_goal_changed': False, 'excluded_from_training': True}
            state_ref = write(STATES / f'layout_seed{layout_seed}.json', value)
            cases.append({'name': f'moka_transfer_original_layout_seed{layout_seed}',
                'episode': value['episode'], 'layout_seed': layout_seed,
                'state_sha256': current_digest, 'registered_layout_state': state_ref,
                'bddl': assets['bddl'], 'init_file': assets['init_file'],
                'instruction': value['instruction'], 'original_instruction': value['instruction'],
                'original_goal_source': True, 'private_original_goal_predicates': task['oracle_goal_predicates'],
                'source': value['source'], 'parent_official_state_sha256': digest(anchor),
                'category': 'moka pot', 'group': 'moka_pot', 'requires_current_visible_unique_binding': True,
                'initial_state_repetition': 0, 'excluded_from_training': True,
                'state_hash_encoding': rule['rawstate_encoding']})
            checks.append({'layout_seed': layout_seed, 'state_sha256': current_digest,
                'changed_flat_indices': changed_indices, 'max_absolute_restore_error': float(np.max(np.abs(state-restored))),
                'initial_original_task_success': initial_done, 'rawstate_dimension': len(state),
                'all_other_rawstate_fields_unchanged': True, 'official_catalog_hash_overlap': False})
    finally:
        env.close()
    cases_ref = write(OUT / 'registered_layout24_candidates.json', {
        'rule': rule_ref, 'cases': cases, 'unique_rawstates': len(seen),
        'registered_before_confirmation': True, 'recipe_status': 'pending selection freeze',
        'rollout_result_used_for_generation': False, 'new_VLA_calls': 0, 'new_training_rows': 0})
    official = json.loads((OUT / 'official_moka_nonoverlap_candidates.json').read_text())
    pending = write(OUT / 'moka_transfer_confirmation100_pending_recipe.json', {
        'purpose': '76 official original rawstates plus24 preregistered original-layout rawstates; pending multi-moka selection and recipe freeze',
        'official_pool': identity(OUT / 'official_moka_nonoverlap_candidates.json'),
        'registered_layout_pool': cases_ref, 'layout_rule': rule_ref,
        'cases': official['cases']+cases, 'source_counts': {'official_original': 76, 'original_layout_perturbation': 24},
        'registered_trials': 100, 'unique_rawstates': len({r['state_sha256'] for r in official['cases']+cases}),
        'duplicate_reset_requests': 0, 'success_threshold': .90, 'public_verifier_agreement_threshold': .95,
        'excluded_from_training': True, 'source_strata_reported_separately': True,
        'recipe_status': 'pending selection freeze and multi-instance public placement conjunction',
        'ready_for_submission': False, 'new_training_rows': 0})
    check_ref = write(OUT / 'layout24_cpu_restore_report.json', {
        'scope': 'CPU no-render simulation initialization and exact rawstate restoration; no VLA or confirmation controls',
        'rule': rule_ref, 'cases': checks, 'prepared': len(cases), 'passed': len(cases)==24,
        'task_goal_changed': False, 'PRO_read': False, 'camera_rendered': False,
        'new_VLA_calls': 0, 'new_training_rows': 0, 'new_confirmation_controls': 0})
    print(json.dumps({'rule': rule_ref, 'layout_candidates': cases_ref,
                      'pending100': pending, 'restore_report': check_ref, 'states': len(cases)}))


if __name__ == '__main__':
    main()
