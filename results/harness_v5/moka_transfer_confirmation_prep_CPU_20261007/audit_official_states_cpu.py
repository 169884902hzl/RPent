"""Audit actual original moka-state use from exact pinned result ledgers."""

import collections
import hashlib
import json
from pathlib import Path


ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
OUT = Path(__file__).resolve().parent / 'preparation'
BASE = ROOT / 'results/harness_v5'
SAFE_INIT = (*range(10, 40), *range(42, 50))


def identity(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def read(path, expected=None):
    ref = identity(path)
    if expected and ref['sha256'] != expected:
        raise ValueError('Pinned source changed: ' + ref['path'])
    return json.loads(Path(ref['path']).read_text()), ref


def write(name, value):
    path = OUT / name
    path.write_text(json.dumps(value, indent=2) + '\n')
    return identity(path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    catalog, catalog_ref = read(BASE / 'collection540_capacity_CPU_20261006/preparation/original130_catalog.json',
        'a6b0e7ba982e6b3ecf276985b804107c349c63861bf165af0ee5ddcc67906be9')
    old, old_ref = read(BASE / 'grasp_runtime546_monitor_CPU_20261006/coord_explicit_access_audit_CPU_20261006/explicit_original_state_exclusions.json',
        '8fd1eeec8c2e5c154f271439a96be80f090e9e38e8b75f1a9588bf2edbf3bedb')
    index, index_ref = read(BASE / 'grasp_runtime546_monitor_CPU_20261006/coord_explicit_access_audit_CPU_20261006/explicit_access_input_index.json',
        'c3333c1333bb7a764f3591b5272844db65689bfa94829219a6619c210170b190')
    moka = [t for t in catalog if 'moka_pot' in t['objects']]
    relevant = {h for task in moka for h in task['state_sha256']}
    episodes = {(t['suite'], t['task'], seed): h for t in moka
                for seed, h in enumerate(t['state_sha256'])}
    baseline = {r['state_sha256']: r for r in old['states'] if r['state_sha256'] in relevant}
    actual_sources = {path for row in baseline.values()
                      for path in row['explicit_source_row_or_registration_counts']
                      if path.endswith('/episodes.jsonl') and '/diagnostic_job' not in path}
    expected = {r['path']: r['sha256'] for r in index['inputs'] if r.get('exists')}
    old_moka, old_moka_ref = read(BASE / 'moka_methods_readonly_CPU_20261006/report/report.json')
    for ref in old_moka['inputs']:
        if '/confirmation_job3685/' in ref['path']:
            actual_sources.add(ref['path'])
            expected[ref['path']] = ref['sha256']
    pan, pan_ref = read(BASE / 'pan559_monitor_CPU_20261006/final_20261006T160044.400615Z/statistic/report.json',
        '1421284ba135b8b5eb0d7297436c72ad9c3f2830edd0cdb80349fd8a3ac8c869')
    for ref in pan['ledger_inputs']:
        if ref['kind'] == 'episodes':
            actual_sources.add(ref['path'])
            expected[ref['path']] = ref['sha256']
    fixtures = BASE / 'skill540_articulate_place_selection/source544_fixtures1200/job4128'
    fixture_sha = [
        '91e5732dc83e2da781cd0c3b1b773a26dee1fd654008aec75e38984299635763',
        'cac6efdef0c0d83140a1588a4d2836395809cb45e977b9bddae65a2f8f7a33b8',
        '1cf5d45a7e0bdfd369cfd8e13f35e40a29912eb5d9dabe0951d7c33b1f9810fa',
        'f1c5a387bc48e552b6e13f4711b3a5ee190c9a3773c74158972a7260475a1c02',
        '68302441669f82950ba573c97d26c1c9931bd36c49bb5406604182aaeef4657d',
        '17a4ebed44cdc6a5104e4aec92cdd51df81500667ea4086268839003879d4647',
        '58817a4b96459777cbd557ae2663e081298b113bf355dc8a3b28114e52a5e080',
        'cd23afba759464cef2305d5def6d49dbb181d0003e11acf9be35834b479a5d92']
    for part, sha in enumerate(fixture_sha):
        path = str(fixtures / f'part{part}/episodes.jsonl')
        actual_sources.add(path)
        expected[path] = sha
    used, source_inputs = collections.defaultdict(list), []
    for path in sorted(actual_sources):
        ref = identity(path)
        if ref['sha256'] != expected[path]:
            raise ValueError('Actual result ledger SHA changed: ' + path)
        rows, identified = 0, 0
        with Path(path).open() as ledger:
            for line_index, line in enumerate(ledger, 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                rows += 1
                case = row.get('case')
                if not isinstance(case, dict):
                    case = row
                ep = case.get('episode', row.get('episode', {}))
                key = ep.get('suite'), ep.get('task'), ep.get('seed')
                if key not in episodes:
                    continue
                digest = episodes[key]
                declared = case.get('state_sha256', row.get('registered_state_sha256'))
                if declared is not None and declared != digest:
                    raise ValueError('Actual ledger has different state bytes: ' + path)
                used[digest].append({'source': ref, 'line': line_index,
                    'episode': ep, 'case': case.get('name'),
                    'usage': 'actual selection or confirmation invocation',
                    'physics_success_not_inferred_from_row_presence': True})
                identified += 1
        source_inputs.append({**ref, 'rows': rows, 'moka_scene_rows': identified})
    candidates, excluded, task_counts, asset_inputs = [], [], [], []
    standard = ROOT / '.venv/lib/python3.10/site-packages/libero/libero'
    import numpy as np
    import torch
    from libero.libero.envs.bddl_utils import get_problem_info
    for task in moka:
        assets = {}
        for kind, directory in [('bddl', 'bddl_files'), ('init_file', 'init_files')]:
            ref = identity(standard / directory / task['suite'] / Path(task[kind]['path']).name)
            if ref['sha256'] != task[kind]['sha256']:
                raise ValueError('Installed standard original asset differs from catalog')
            assets[kind] = ref
            asset_inputs.append(ref)
        bddl = get_problem_info(assets['bddl']['path'])
        language = bddl['language_instruction']
        if isinstance(language, list):
            language = ' '.join(language)
        states = torch.load(assets['init_file']['path'], weights_only=False)
        if len(states) != 50:
            raise ValueError('Official original state count changed')
        goal = [g for g in task['oracle_goal_predicates']
                if len(g) == 3 and g[0] == 'on' and 'moka' in g[1]]
        counts = collections.Counter()
        for seed, state in enumerate(states):
            digest = hashlib.sha256(np.asarray(state, dtype='<f8', order='C').tobytes()).hexdigest()
            if digest != task['state_sha256'][seed]:
                raise ValueError('Standard raw state differs from catalog')
            ep = {'suite': task['suite'], 'task': task['task'], 'seed': seed}
            row = {'episode': ep, 'state_sha256': digest, 'official_init_index': seed,
                'instruction': language, 'original_instruction': language,
                'bddl': assets['bddl'], 'init_file': assets['init_file'],
                'private_original_goal_predicates': task['oracle_goal_predicates'],
                'selected_moka_On_predicates': goal, 'original_goal_source': bool(goal),
                'category': 'moka pot', 'group': 'moka_pot',
                'state_hash_encoding': 'C contiguous little endian float64',
                'requires_current_visible_unique_binding': True,
                'excluded_from_training': True, 'initial_state_repetition': 0}
            reasons = []
            if seed not in SAFE_INIT:
                reasons.append('public_dev_final_reserved_init_0_9_40_41')
                counts['public_reserved'] += 1
            if digest in used:
                reasons.append('actual_prior_selection_or_confirmation')
                counts['actual_prior_use'] += 1
            if reasons:
                excluded.append({**row, 'reasons': reasons, 'actual_use_evidence': used.get(digest, []),
                    'old_exclusion_source_tags': baseline.get(digest, {}).get('explicit_source_row_or_registration_counts', {})})
            else:
                candidates.append(row)
                counts['candidate_unique_raw_states'] += 1
                counts['original_target_candidates' if goal else 'counterfactual_scene_candidates'] += 1
        task_counts.append({'suite': task['suite'], 'task': task['task'],
                            'original_instruction': language, 'has_moka_On_original_goal': bool(goal), **counts})
    old_only = [digest for digest, record in baseline.items()
                if all(not source.endswith('/episodes.jsonl') for source in record['explicit_source_row_or_registration_counts'])]
    recovered = [digest for digest in old_only if digest not in used
                 and any(c['state_sha256'] == digest for c in candidates)]
    assert len({r['state_sha256'] for r in candidates}) == len(candidates)
    pool = write('official_moka_nonoverlap_candidates.json', {
        'cases': candidates, 'unique_raw_states': len(candidates), 'target': 100,
        'shortfall': max(0, 100-len(candidates)), 'not_submitted': True,
        'duplicate_reset_requests': 0, 'official_layout_perturbations_generated': 0,
        'public_safe_init_indices': list(SAFE_INIT),
        'full_original_instruction_goal_scope_pending_for_multi_moka_scene': True,
        'original_and_counterfactual_scene_counts': task_counts})
    exclusion_ref = write('actual_selection_confirmation_exclusions.json', {
        'states': excluded, 'source_inputs': source_inputs,
        'metadata_read_only_pool_reservations_are_not_actual_use': True,
        'sealed_payload_read': False, 'PRO_payload_read': False, 'human_or_training_text_read': False})
    report = write('official_pool_audit_report.json', {
        'inputs': [catalog_ref, old_ref, index_ref, old_moka_ref, pan_ref],
        'installed_standard_assets': asset_inputs, 'actual_ledger_inputs': source_inputs,
        'per_task': task_counts, 'all_moka_scenes_official_states': 400,
        'actual_prior_used_moka_rawstates': len(used), 'candidate_unique_rawstates': len(candidates),
        'target': 100, 'shortfall': max(0, 100-len(candidates)),
        'old_metadata_only_moka_rawstates': len(old_only),
        'old_metadata_only_states_also_proven_actually_used': sum(bool(used.get(h)) for h in old_only),
        'recovered_candidate_rawstates_after_actual_use_audit': recovered,
        'candidate_pool': pool, 'exclusions': exclusion_ref,
        'scope': 'Exact named selection/confirmation result ledgers; no all-history completeness claim. Later unpublished reservations must be checked before final confirmation.',
        'public_reserved_source': 'Current skill544 SAFE_INIT convention: original indices0-9/40/41 excluded; sealed payload not opened',
        'new_physics': 0, 'new_model_calls': 0, 'new_training_rows': 0})
    print(json.dumps({'report': report, 'pool': pool, 'candidates': len(candidates),
                      'shortfall': max(0,100-len(candidates)), 'per_task': task_counts}))


if __name__ == '__main__':
    main()
