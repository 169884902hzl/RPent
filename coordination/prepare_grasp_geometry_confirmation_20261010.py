"""Use a fixed method on predeclared, unused confirmation states; no skill replay."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def pin(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def registered_view_axes(plan, evidence, needed):
    """Reuse the selection compiler's camera axes, without executing a skill."""
    axes, inputs = {}, []
    report = json.loads(evidence.read_text())

    def plans():
        yield plan
        for value in report['groups'].values():
            path = Path(value['plan']['path'])
            if pin(path)['sha256'] != value['plan']['sha256']:
                raise ValueError('selection reference plan changed')
            yield json.loads(path.read_text())

    for candidate in plans():
        for case in candidate['cases']:
            key = case['bddl']['sha256']
            if key not in needed or key in axes:
                continue
            ref = case['registered_layout_state']
            path = Path(ref['path'])
            if pin(path)['sha256'] != ref['sha256']:
                raise ValueError('selection reference state changed')
            state = json.loads(path.read_text())
            value = state.get('source_reference_compilation', {}).get('view_axes')
            if value:
                axes[key] = value
                inputs.append(pin(path))
        if needed <= axes.keys():
            return axes, inputs
    raise ValueError('registered selection camera axes missing for confirmation scene')


def main():
    from scripts.prepare_v5_perturb_skill_selection_20261009 import public_name
    from scripts.v5_perturb_public_reference import source_reference

    parser = argparse.ArgumentParser()
    parser.add_argument('--parent-plan', type=Path, required=True)
    parser.add_argument('--pool', type=Path, required=True)
    parser.add_argument('--selection-evidence', type=Path, required=True)
    parser.add_argument('--selection-states', type=Path, required=True)
    parser.add_argument('--launcher', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    plan, pool = json.loads(args.parent_plan.read_text()), json.loads(args.pool.read_text())
    if plan['confirmation'] or plan['training_allowed'] or plan['PRO_files_read']:
        raise ValueError('expected an original-task selection method')
    if (not pool['permanent_training_exclusion'] or pool['policy_outcomes_read']
            or pool['PRO_files_read'] or pool['skill_executions']):
        raise ValueError('confirmation pool already used or not permanently isolated')
    # The remote coordination tree is deliberately not a runtime checkout.
    # Resolve category names using this method's pinned implementation.
    sys.path.insert(0, plan['source_path'])
    prepared = [r for r in pool['rows'] if r['status'] == 'prepared']
    if len(prepared) < 100:
        raise ValueError('at least 100 predeclared valid, unused states required')
    # Preserve declaration order. Geometric layout validity was assessed
    # before any skill ran; it is not a policy-based selection filter.
    chosen = prepared[:100]
    category = plan['cases'][0]['type'].removeprefix('grasp_')
    if any(r['rule']['category'] != category for r in chosen):
        raise ValueError('method and confirmation pool categories differ')
    selection_hashes = {r['state_sha256'] for r in map(json.loads, args.selection_states.open())}
    if len({r['state_sha256'] for r in chosen}) != 100 or any(
            r['state_sha256'] in selection_hashes for r in chosen):
        raise ValueError('duplicate or selection-overlapping confirmation state')
    if any(not r['permanent_training_exclusion'] or r['policy_outcomes_read']
            or r['PRO_files_read'] or r['skill_executed'] for r in chosen):
        raise ValueError('confirmation state used before method locking')
    axes, axis_inputs = registered_view_axes(
        plan, args.selection_evidence, {r['bddl']['sha256'] for r in chosen})
    args.output.mkdir(parents=True, exist_ok=False)
    producer = args.output / Path(__file__).name
    producer.write_bytes(Path(__file__).read_bytes())
    old_condition, condition = next(iter(plan['conditions'].items()))
    condition_name = 'confirmation_' + old_condition
    template = plan['cases'][0]
    cases = []
    for row in chosen:
        state_path = Path(row['registered_layout_state']['path'])
        if pin(state_path)['sha256'] != row['registered_layout_state']['sha256']:
            raise ValueError('confirmation reset changed before instruction compilation')
        state = json.loads(state_path.read_text())
        geometry = state['preparation_provenance']['settled_geometry']
        names = {symbol: public_name(symbol) for symbol in geometry}
        view_axes = axes[row['bddl']['sha256']]
        reference = source_reference(row['source_symbol'], geometry, view_axes, names)
        instruction = 'pick up ' + (reference or 'the ' + public_name(row['source_symbol']))
        state['diagnostic_instruction'] = instruction
        state['source_reference_compilation'] = {
            'version': 'original_layout_plain_reference/2', 'reference': reference,
            'view_axes': view_axes, 'geometry_use': 'task sentence construction only',
            'minimum_axis_gap_m': .04, 'policy_outcomes_used': False,
            'state_bytes_changed': False, 'ambiguous_cases_retained': True}
        compiled_state = args.output / (row['name'] + '_public_reference.json')
        compiled_state.write_text(json.dumps(state, indent=2, allow_nan=False) + '\n')
        case = copy.deepcopy(template)
        case.update(name=row['name'] + '_' + old_condition, episode=row['episode'],
            state_sha256=row['state_sha256'], registered_layout_state=pin(compiled_state),
            object_symbol=row['source_symbol'], object_category=row['source_category'],
            bddl=row['bddl'], init_file=row['init_file'],
            subtask_prompt=instruction, compiled_public_instruction=True,
            original_instruction=row['original_instruction'], changed_goal=row['changed_goal'],
            layout_seed=row['layout_seed'], confirmation=True, training_allowed=False,
            condition=condition_name, permanent_training_exclusion=True,
            confirmation_pool_row_name=row['name'])
        case.pop('paired_baseline_case', None)
        cases.append(case)
    plan.update(version='locked-v3-geometric-grasp-confirmation/2', cohort='confirmation',
        cases=cases, conditions={condition_name: condition}, producer=pin(producer),
        producer_dependencies=[pin(producer), *plan['producer_dependencies']], confirmation=True, qualification_authorized=True,
        training_allowed=False, new_training_rows=0, PRO_files_read=False,
        method_selected_using_selection_outcomes=True,
        confirmation_states_selected_using_policy_outcomes=False,
        policy_outcomes_used_for_selection=False, parent_plan=pin(args.parent_plan),
        selection_evidence=pin(args.selection_evidence), confirmation_pool=pin(args.pool),
        selection_exclusion=pin(args.selection_states),
        invalid_preparations=[r for r in pool['rows'] if r['status'] != 'prepared'],
        invalid_preparations_retained=True, valid_unselected_reserves=prepared[100:],
        layout_states=[c['registered_layout_state'] for c in cases],
        physical_selection_state_bytes_unchanged=False,
        purpose='Independent confirmation of a method fixed before reading any confirmation outcome; locked v3.')
    plan['references'] = [*plan['references'], pin(args.pool), pin(args.selection_evidence),
        pin(args.selection_states), *axis_inputs]
    plan['producer_dependencies'].extend([
        pin(Path(source_reference.__code__.co_filename)), pin(Path(public_name.__code__.co_filename))])
    plan_path = args.output / 'confirmation.json'
    plan_path.write_text(json.dumps(plan, indent=2) + '\n')
    env = dict(os.environ, PERTURB_SKILL_PLAN=str(plan_path.resolve()),
        PERTURB_SKILL_PLAN_SHA=pin(plan_path)['sha256'], PERTURB_SKILL_SOURCE=plan['source_path'],
        PERTURB_SKILL_ADAPTER=plan['adapter_path'], PERTURB_SKILL_OUTPUT=str(args.output.parent.resolve()),
        PERTURB_SKILL_STARTUP='1', PERTURB_SKILL_CPU_ONLY='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    result = subprocess.run(['bash', str(args.launcher.resolve())], cwd='/tmp', env=env,
        capture_output=True, text=True)
    (args.output / 'CPU_preflight.log').write_text(result.stdout + result.stderr)
    result.check_returncode()
    manifest = {'plan': pin(plan_path), 'pool': pin(args.pool), 'method_parent': pin(args.parent_plan),
        'source_identity': pin(Path(plan['source_path']) / 'source_identity_v3r9.json'),
        'launcher': pin(args.launcher), 'registered_n': 100,
        'pool_invalid_layouts_retained': len(plan['invalid_preparations']),
        'selection_overlap': 0, 'order': 'first100_predeclared_prepared_rows',
        'permanent_training_exclusion': True, 'CPU_preflight': result.stdout,
        'all_pool_layout_seeds_permanently_excluded': [r['layout_seed'] for r in pool['rows']],
        'physical_execution': False, 'startup_submitted': False, 'training_allowed': False,
        'python': sys.executable}
    (args.output / 'preparation_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'registered_n': 100, 'plan': manifest['plan'], 'physical_execution': False}))


if __name__ == '__main__':
    main()
