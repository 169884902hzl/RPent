"""Compare grasp methods with explicit source language on fixed layouts."""

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
SOURCE = ROOT / 'source_v5_public_references_20261009_r1'
ADAPTER = ROOT / 'coordination/perturb_public_reference_adapter_20261009_r1'
PREVIOUS = ROOT / 'results/harness_v5/perturb_skill_selection_20261009_r1'
OUTPUT = ROOT / 'results/harness_v5/perturb_grasp_public_reference_20261009_r2'


def ref(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    import numpy as np
    from libero.libero.envs import OffScreenRenderEnv
    from robosuite.utils.camera_utils import get_camera_extrinsic_matrix
    from scripts.prepare_v5_perturb_skill_selection_20261009 import public_name
    from scripts.v5_perturb_public_reference import source_reference

    if os.environ.get('LIBERO_TYPE') != 'standard':
        raise ValueError('original-only geometry required')
    snapshot = json.loads((SOURCE / 'source_snapshot.json').read_text())
    if ref(Path(snapshot['archive']['path'])) != snapshot['archive']:
        raise ValueError('source archive changed')
    launcher = ADAPTER / 'scripts/run_v5_perturb_skill_selection_20261009.sbatch'
    wrappers = {}
    try:
        for category in ('bowl', 'bottle', 'box', 'cup', 'frypan'):
            cell = 'grasp_' + category
            prep = OUTPUT / cell / 'preparation'
            prep.mkdir(parents=True, exist_ok=False)
            old_path = PREVIOUS / cell / 'preparation/selection.json'
            old = json.loads(old_path.read_text())
            originals = [c for c in old['cases'] if c['condition'] == 'current160']
            if len(originals) != 100:
                raise ValueError('same100 declared selection layouts required')
            current = copy.deepcopy(old['conditions']['current160'])
            contact = copy.deepcopy(old['conditions']['wrist_near_contact160'])
            contact['overrides'].update(grasp_wrist_contact_v3=True, grasp_short_prompt_v2=True)
            conditions = {'current_public_reference160': current, 'wrist_contact5cm_public_reference160': contact}
            cases, compilation = [], []
            for original in originals:
                state_ref = original['registered_layout_state']
                path = Path(state_ref['path'])
                if ref(path) != state_ref:
                    raise ValueError('selection reset changed')
                state = json.loads(path.read_text())
                bddl = state['bddl']['path']
                if bddl not in wrappers:
                    wrapper = wrappers[bddl] = OffScreenRenderEnv(bddl_file_name=bddl,
                                                                  camera_heights=256, camera_widths=256)
                    wrapper.reset()
                wrapper = wrappers[bddl]
                wrapper.set_init_state(np.asarray(state['rawstate']))
                rotation = get_camera_extrinsic_matrix(wrapper.sim, 'agentview')[:3, :3]
                axes = []
                for column in (0, 1):
                    axis = rotation[:, column].copy(); axis[2] = 0
                    axis /= np.linalg.norm(axis)
                    axes.append(axis.tolist())
                geometry = state['preparation_provenance']['settled_geometry']
                names = {name: public_name(name) for name in geometry}
                reference = source_reference(state['source_symbol'], geometry, axes, names)
                # Keep unclear references in the declared denominator; the
                # controller must still bind or fail from its public perception.
                instruction = 'pick up ' + (reference or f"the {public_name(state['source_symbol'])}")
                state['diagnostic_instruction'] = instruction
                state['source_reference_compilation'] = {
                    'version': 'original_layout_plain_reference/2', 'reference': reference,
                    'view_axes': axes, 'geometry_use': 'task sentence construction only',
                    'minimum_axis_gap_m': .04, 'policy_outcomes_used': False,
                    'state_bytes_changed': False, 'ambiguous_cases_retained': True}
                state_name = original['name'].removesuffix('_current160')
                reset = prep / (state_name + '_public_reference.json')
                reset.write_text(json.dumps(state, indent=2, allow_nan=False) + '\n')
                compilation.append({'name': state_name, 'reference': reference, 'instruction': instruction,
                                    'state_sha256': state['state_sha256']})
                for method in conditions:
                    case = copy.deepcopy(original)
                    case.update(name=case['name'].removesuffix('_current160') + '_' + method,
                                condition=method, subtask_prompt=instruction, compiled_public_instruction=True,
                                registered_layout_state=ref(reset))
                    cases.append(case)
            compilation_path = prep / 'source_reference_compilation.json'
            compilation_path.write_text(json.dumps(compilation, indent=2) + '\n')
            dependencies = [ref(ADAPTER / 'scripts' / name) for name in (
                'probe_v5_perturb_skill_20261009.py', 'v5_perturb_goal_diagnostic.py',
                'v5_perturb_public_reference.py', 'prepare_v5_perturb_skill_selection_20261009.py')]
            plan = {**old, 'source_path': str(SOURCE), 'source_snapshot': snapshot,
                    'source_commit': snapshot['commit'], 'adapter_path': str(ADAPTER),
                    'cases': cases, 'conditions': conditions, 'producer': ref(Path(__file__)),
                    'producer_dependencies': [ref(Path(__file__)), *dependencies],
                    'references': [*old['references'], ref(old_path), ref(compilation_path)],
                    'ambiguous_source_references': sum(row['reference'] is None for row in compilation),
                    'physical_selection_state_bytes_unchanged': True,
                    'purpose': 'grasp selection with explicit public source sentence; current vs wrist5cm contact',
                    'confirmation': False, 'training_allowed': False}
            manifest = prep / 'selection.json'
            manifest.write_text(json.dumps(plan, indent=2) + '\n')
            env = {'PERTURB_SKILL_PLAN': str(manifest), 'PERTURB_SKILL_PLAN_SHA': ref(manifest)['sha256'],
                   'PERTURB_SKILL_SOURCE': str(SOURCE), 'PERTURB_SKILL_ADAPTER': str(ADAPTER),
                   'PERTURB_SKILL_OUTPUT': str(OUTPUT / cell), 'PERTURB_SKILL_STARTUP': '1'}
            cpu = subprocess.run(['bash', str(launcher)], env={**os.environ, **env,
                                 'PERTURB_SKILL_CPU_ONLY': '1'}, capture_output=True, text=True)
            (prep / 'CPU_preflight.log').write_text(cpu.stdout + cpu.stderr)
            cpu.check_returncode()
            command = ['sbatch', '--parsable', '--array=0',
                       '--export=ALL,' + ','.join(k + '=' + v for k, v in env.items()), str(launcher)]
            job = subprocess.run(command, text=True, capture_output=True, check=True).stdout.strip()
            record = {'job': job, 'environment': env, 'launcher': ref(launcher), 'manifest': ref(manifest),
                      'CPU_preflight': 'pass', 'physical_startup': 'pending', 'confirmation': False}
            (prep / 'startup_submission.json').write_text(json.dumps(record, indent=2) + '\n')
            print(json.dumps({'cell': cell, 'job': job, 'ambiguous_source_references': plan['ambiguous_source_references']}), flush=True)
    finally:
        for wrapper in wrappers.values():
            wrapper.close()


if __name__ == '__main__':
    main()
