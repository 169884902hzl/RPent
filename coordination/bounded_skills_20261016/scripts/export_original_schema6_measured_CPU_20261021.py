"""Export closed original-only forks with exact measured-label bindings."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import pickle
import sys


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def reference(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def verify_trial_context(trial, choices, request, initial_physics_sha256):
    """A recovered later decision cannot label the original request."""
    if trial['initial_physics_sha256'] != initial_physics_sha256:
        return False, 'different_initial_physics'
    if trial['request_sha256'] != digest(request):
        return False, 'different_initial_request'
    selected = trial.get('selected_candidate_id')
    if selected is None:
        return False, 'no_bound_candidate_selected'
    chosen = next((row for row in choices
                   if selected in row['decision']['candidate_ids']), None)
    if chosen is None or chosen['index'] != 0 or digest(chosen['request']) != digest(request):
        return False, 'selection_after_context_changed'
    return True, None


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--results', type=Path, required=True)
    p.add_argument('--policy-hashes', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--allow-incomplete', action='store_true', help='Preview; pending cases remain explicitly unresolved')
    p.add_argument('--digest-accelerator', type=Path)
    p.add_argument('--digest-accelerator-sha256')
    a = p.parse_args()
    if bool(a.digest_accelerator) != bool(a.digest_accelerator_sha256):
        p.error('a canonical digest accelerator requires its registered SHA256')
    sys.path.insert(0, str(a.source.resolve(strict=True)))
    from robots.libero.bounded_hybrid_diagnostic import snapshot_digest
    from rpent.skill_package.contract import action_binding_required, legal_after, method_family
    from scripts.bounded_state_exclusions import check_exclusions
    digest_tool = None
    if a.digest_accelerator is not None:
        import importlib.util
        digest_tool = reference(a.digest_accelerator)
        if digest_tool['sha256'] != a.digest_accelerator_sha256:
            raise ValueError('registered canonical digest accelerator changed')
        spec = importlib.util.spec_from_file_location('canonical_snapshot_digest_tool', a.digest_accelerator)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        snapshot_digest = module.snapshot_digest

    plan = json.loads(a.manifest.read_bytes())
    if json.loads((a.source / 'SOURCE_REVISION.json').read_bytes())['commit'] != plan['source_commit']:
        raise ValueError('runtime snapshot revision differs from registered fork source')
    if plan['training'] or plan['confirmation']:
        raise ValueError('expected original development fork manifest')
    if any(c['diagnostic']['domain'] != 'original' for c in plan['cases']):
        raise ValueError('PRO/D2 cannot enter this label export')
    check_exclusions(plan['cases'], plan['permanent_exclusions'])
    hashes = {}
    for line in a.policy_hashes.read_text().splitlines():
        sha, name = line.split(maxsplit=1)
        hashes[Path(name).name] = sha
    if set(hashes) != {'model.safetensors', 'metadata.pt'}:
        raise ValueError('actual policy weight and metadata hashes required')
    policy_revision = 'pi05-libero-sha256:' + digest(hashes)
    records, unresolved = [], []
    categories = Counter()
    for case in plan['cases']:
        matches = [f for f in a.results.glob('job*/N8/*/worker_summary.json')
                   if json.loads(f.read_bytes())['case']['name'] == case['name']]
        if not matches and a.allow_incomplete:
            unresolved.append({'case': case['name'], 'reason': 'pending_not_failure'})
            continue
        if len(matches) != 1:
            raise ValueError('one closed worker required per registered case: ' + case['name'])
        worker_path = matches[0]
        worker = json.loads(worker_path.read_bytes())
        result = worker['result']
        if worker['case'] != case or worker['source_commit'] != plan['source_commit']:
            raise ValueError('worker source/case binding changed')
        root = worker_path.parent / case['name']
        start = root / 'private_branchpoint.pkl'
        if not start.exists():
            unresolved.append({'case': case['name'], 'reason': result.get('reason', result['status']),
                               'source': reference(worker_path)})
            continue
        saved = pickle.loads(start.read_bytes())
        if saved['public_runtime']['adapter'].get('vla_options_v2', False) != plan.get('vla_options_v2', False):
            raise ValueError('captured B2 catalog differs from its registration')
        if saved['physics']['actuator_state'].get('integration') is None:
            raise ValueError('new measured labels require complete integration state')
        request = saved['request']
        initial_sha = snapshot_digest(saved['physics'])
        legal = set(legal_after(request, []))
        by_id = {c['id']: c for c in request['candidates']}
        trials = result['trials']
        specs = {digest(t['subtask']) for t in trials}
        if len(specs) != 1:
            raise ValueError('trial subtask contracts differ')
        spec = trials[0]['subtask']
        contract = {'version': 'original-subtask-measured/1', 'subtask': spec,
                    'pick': 'private_sustained_grasp_v3_post_branch_window',
                    'other_modes': 'unchanged_registered_task_predicate',
                    'self_continuation': 'bounded oracle until registered subtask or budget',
                    'vla_budget': case['diagnostic']['budget'],
                    'truth_code': reference(a.source / 'robots/libero/v5_grasp_truth.py')}
        if plan.get('vla_options_v2'):
            contract['full_task_call_vla'] = 'unchanged_native_task_completion; not sustained-grasp truth'
        binding = {'request_sha256': digest(request), 'prefix': [],
                   'snapshot_sha256': reference(start)['sha256'],
                   'outcome_contract_sha256': digest(contract),
                   'source_revision': plan['source_commit']}
        context_sha = digest(binding)
        branches = {}
        unknown = []
        for trial in trials:
            choices_ref = trial['choices']
            if reference(choices_ref['path']) != choices_ref:
                raise ValueError('trial choices changed')
            choices = [json.loads(line) for line in Path(choices_ref['path']).read_bytes().splitlines()]
            verified, reason = verify_trial_context(trial, choices, request, initial_sha)
            cid = trial.get('selected_candidate_id')
            if cid not in legal or not verified:
                unknown.append({'trial_seed': trial['trial_seed'], 'reason': reason or 'candidate_not_initial_legal',
                                'original_reason': trial['reason'], 'source': choices_ref})
                continue
            candidate = by_id[cid]
            family = method_family(candidate)
            required = action_binding_required(candidate)
            resolved = trial['source_public_id'] is not None
            if candidate['parameters'].get('target_id'):
                resolved = resolved and trial['target_public_id'] is not None
            status = 'resolved' if required and resolved else 'missing' if required else 'not_applicable'
            if cid not in branches:
                branches[cid] = {'candidate_id': cid, 'method_family': family,
                                 'action_binding_requirement': 'required' if required else 'not_required',
                                 'trials': []}
                if family == 'vla':
                    branches[cid]['policy_revision'] = policy_revision
            inputs = trial.get('vla_inputs', [])
            executions = [detail['execution'] for row in choices
                          for detail in row.get('execution_details', [])
                          if detail.get('candidate_id') == cid and 'execution' in detail]
            prompts = sorted({e['template']['prompt'] for e in executions if 'template' in e})
            if inputs:
                if len(prompts) != 1:
                    raise ValueError('invoked VLA needs one actual execution prompt')
                wire_hash = hashlib.sha256(json.dumps([prompts[0]], sort_keys=True).encode()).hexdigest()
                if any(x['fields']['task_descriptions'] != wire_hash for x in inputs):
                    raise ValueError('rendered prompt differs from actual inference wire input')
            evidence = trial['evidence']
            if reference(evidence['path']) != evidence:
                raise ValueError('private trial truth changed')
            audit = {'trial': trial, 'candidate': candidate, 'actual_policy_hashes': hashes,
                     'choices': choices_ref, 'wire_inputs': inputs, 'execution_prompts': prompts}
            invocation = f'{cid}_' if plan.get('vla_options_v2') else ''
            audit_path = root / f'label_invocation_{invocation}{trial["trial_seed"]}.json'
            if audit_path.exists():
                if json.loads(audit_path.read_bytes()) != audit:
                    raise ValueError('invocation audit changed')
            else:
                audit_path.write_bytes(canonical(audit) + b'\n')
            entry = {'sample_id': f'{case["name"]}/{cid if plan.get("vla_options_v2") else trial["method"]}/{trial["trial_seed"]}',
                     'seed': trial['trial_seed'], 'status': 'closed', 'success': trial['success'],
                     'wall_s': max(0., trial['wall_s']-trial.get('private_metrology_s', 0.)),
                     'raw_wall_s': trial['wall_s'], 'private_metrology_s': trial.get('private_metrology_s', 0.),
                     'wall_scope': 'runtime excludes private post-branch metrology',
                     'sim_steps': trial['sim_steps'], 'reason': trial['reason'],
                     'state_binding_verified': True, 'context_sha256': context_sha,
                     'action_binding_status': status, 'evidence': evidence,
                     'invocation_evidence': reference(audit_path)}
            if family == 'vla':
                # A pre-inference rejection is a real attempted failure, but
                # does not contain an effective prompt observed on the wire.
                entry['effective_prompt_sha256'] = hashlib.sha256(prompts[0].encode()).hexdigest() if inputs else None
                entry['prompt_wire_status'] = 'observed' if inputs else 'not_invoked'
            branches[cid]['trials'].append(entry)
        own_layout = case['diagnostic'].get('own_layout')
        row = {'version': 'measured-subtask-choice/2',
               'record_id': ('own-layout-schema6-measured/' if own_layout else 'original-schema6-measured/')
                   + case['name'] + '/' + binding['snapshot_sha256'][:16],
               'public_request': request, 'prefix': [], 'binding': binding,
               'branches': list(branches.values()), 'unknown_trials': unknown,
               'outcome_contract': contract, 'snapshot': reference(start), 'source': reference(worker_path),
               'source_rule_result': {'status': 'unknown', 'reason': 'not_recorded_for_this_new_capture'},
               'domain': 'libero_original90' if case['episode']['suite'] == 'libero_90' else 'libero_original40',
               'PRO': False, 'confirmation': False, 'source_split': 'train',
               'source_training_parent_ids': case['source_training_parent_ids'], 'case': case,
               'source_episode_id': case['name'], 'initial_state_sha256': case['state_sha256'],
               'parent_links_scope': 'frozen initial-state split identity only; not old request/prefix compatibility',
               'origin_episode_success': None, 'origin_episode_success_reason': 'subtask forks do not establish whole-episode outcome',
               'scope': 'same-state subtask outcome with method continuation; not immediate first-action success'}
        if own_layout:
            row.update(identity_domain='own_original_train_layout', own_layout=own_layout,
                initial_state_sha256_scope='original train root for split lineage; actual constructed state is binding.snapshot_sha256',
                parent_links_scope='original train task lineage plus registered own layout; no old request or outcome labels transferred')
        records.append(row)
        categories[case['category']] += 1
    a.output.mkdir(parents=True, exist_ok=False)
    data = a.output / 'positions.jsonl'
    data.write_bytes(b''.join(canonical(r) + b'\n' for r in records))
    report = {'version': 'measured-subtask-choice/2', 'source_revision': plan['source_commit'],
              'positions': len(records), 'registered_cases': len(plan['cases']), 'preview': a.allow_incomplete,
              'by_category': dict(categories), 'unresolved_cases': unresolved,
              'policy_revision': policy_revision, 'policy_hashes': hashes, 'data': reference(data),
              'manifest': reference(a.manifest), 'PRO': False, 'confirmation': False,
              'B2_new_catalog_active': bool(plan.get('vla_options_v2')), 'training_executed': False,
              'release_scope': 'only executed candidates acquire measured labels; all others remain unknown; no model training executed'}
    if digest_tool is not None:
        report['canonical_digest_accelerator'] = digest_tool
    (a.output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
