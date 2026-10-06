"""Read only explicit original manifest/ledger references; never enumerate artifacts."""

import hashlib
import json
import os
import re
from collections import Counter, defaultdict, deque
from pathlib import Path


ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASE = ROOT / 'results/harness_v5/grasp_runtime546_monitor_CPU_20261006'
OUT = BASE / 'coord_explicit_access_audit_CPU_20261006'
COORD = Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md')
BASELINE = BASE / 'extended_original90_pan_explicit_access_pool_v2_CPU_20261006/report.json'
ACCESS529 = ROOT / 'results/harness_v5/original90_access529_CPU_20261005/report/report.json'
ESTIMATE540 = ROOT / 'results/harness_v5/collection540_capacity_CPU_20261006/preparation/estimate_index_complete_known.json'
MONITOR = BASE / 'monitor_jobs_index.json'
EXTRA = OUT / 'named_coordination_registration_index.json'
os.environ['LIBERO_TYPE'] = 'standard'
os.environ['LIBERO_CONFIG_PATH'] = str(ROOT / 'runtime_config')
import numpy as np
from rlinf.envs.libero.utils import benchmark


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def absolute(path):
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def allowed(path):
    """Only registration metadata and episode ledgers, not catalogs or payloads."""
    path = str(path)
    tail = Path(path).name
    if not path.startswith(str(ROOT / 'results/harness_v5') + '/'):
        return False
    if any(x in path.lower() for x in ('sealed', 'manual', 'train', 'pro_training')):
        return False
    if '/development_part' in path or '_swap/' in path or '_swap_' in path:
        return False
    if tail == 'episodes.jsonl':
        return True
    if not path.endswith('.json'):
        return False
    if tail == 'states.json' or any(x in tail for x in ('catalog', 'metadata', 'choices', 'audit', 'report')):
        return False
    if '/preparation' in path:
        return True
    return any(x in tail for x in ('selection', 'sampling', 'candidate_pool', 'development10'))


raw = COORD.read_bytes()
lines = raw.decode().splitlines()
refs = defaultdict(list)
unresolved_paths, sha_contexts = [], []
heading = ''
path_re = re.compile(r'(?:/public/home/sunyihan/rpent_libero_eval/)?results/harness_v5/[A-Za-z0-9_./${}<>-]+\.jsonl?')
for i, line in enumerate(lines, 1):
    if line.startswith('#'):
        heading = line
    paths = path_re.findall(line)
    selected = []
    for path in paths:
        path = str(absolute(path))
        if not allowed(path):
            continue
        if any(c in path for c in ('$', '{', '}', '<', '>')) or '..' in path:
            unresolved_paths.append({'coord_line': i, 'path': path, 'reason': 'nonconcrete_template'})
            continue
        refs[path].append(i)
        selected.append(path)
    if re.search(r'manifest|清单|注册', line, re.I) and re.search(r'\b[0-9a-f]{64}\b', line):
        sha_contexts.append({'coord_line': i, 'sha256s': re.findall(r'\b[0-9a-f]{64}\b', line),
                             'explicit_paths': selected, 'heading': heading, 'context': line})
coord_descriptor = {'path': str(COORD), 'sha256': hashlib.sha256(raw).hexdigest(),
                    'lines': len(lines), 'bytes': len(raw)}
OUT.mkdir(exist_ok=True)
(OUT / 'coordination_path_registry.json').write_text(json.dumps({
    'coordination': coord_descriptor,
    'references': [{'path': p, 'coord_lines': n, 'kind': 'explicit_ledger' if p.endswith('.jsonl') else 'manifest_or_index_reference'}
                   for p,n in sorted(refs.items())],
    'manifest_sha_contexts': sha_contexts, 'unresolved_path_templates': unresolved_paths,
    'no_artifact_directory_scan': True, 'no_PRO_or_sealed_files_read': True}, indent=2) + '\n')

baseline = json.loads(BASELINE.read_text())
assert digest(BASELINE) == 'ae503a55a7a8b3d6e22090abd9aecd8a4a8f4277657c8443c8ff9448a108be7d'
prior = baseline['eligible_cases']
prior_by_sha = {r['state_sha256']: r for r in prior}
prior_by_tuple = {(r['episode']['suite'], r['episode']['task'], r['episode']['seed']):r for r in prior}
queue, descriptors, missing, skips, case_gaps = deque(), {}, [], [], []
excluded_states, excluded_tuples, removals = set(), set(), defaultdict(list)
state_cache, benchmarks = {}, {}
all_sources_by_sha, all_tuples_by_sha = defaultdict(Counter), defaultdict(set)
launcher_inputs = []
loaded = set()


def enqueue(path, origin, expected=None, expected_rows=None, trusted_index=False):
    path = str(absolute(path))
    if not trusted_index and not allowed(path):
        skips.append({'path': path, 'origin': origin, 'reason': 'not_original_registration_or_ledger'})
        return
    d = descriptors.setdefault(path, {'path': path, 'references': []})
    d['references'].append({'origin': origin, 'expected_sha256': expected, 'expected_rows': expected_rows})
    if path not in loaded:
        queue.append(path)


def exclude(case, path, label):
    if not isinstance(case, dict):
        return False
    episode = case.get('episode')
    if episode is None and all(k in case for k in ('suite', 'task', 'seed')):
        episode = {k: case[k] for k in ('suite', 'task', 'seed')}
    state_hash = case.get('state_sha256') or case.get('scene_state_sha256') or case.get('initial_state_sha256')
    if not isinstance(state_hash, str):
        # Per-task catalog hash arrays do not establish a visit or reservation.
        state_hash = None
    hashes, key = {state_hash} if state_hash else set(), None
    if episode and all(k in episode for k in ('suite', 'task', 'seed')):
        suite = episode['suite']
        if suite not in ('libero_90', 'libero_10', 'libero_goal', 'libero_spatial', 'libero_object'):
            case_gaps.append({'source': path, 'case': label, 'episode': episode, 'reason': 'not_original_suite_not_read'})
            return False
        key = (suite, int(episode['task']), int(episode['seed']))
        excluded_tuples.add(key)
        if key not in state_cache:
            try:
                if suite not in benchmarks:
                    benchmarks[suite] = benchmark.get_benchmark(suite)()
                states = benchmarks[suite].get_task_init_states(key[1])
                a = np.asarray(states[key[2]], dtype='<f8', order='C')
                state_cache[key] = hashlib.sha256(a.tobytes()).hexdigest()
            except (KeyError, IndexError, ValueError) as error:
                case_gaps.append({'source': path, 'case': label, 'episode': episode, 'reason': str(error)})
                state_cache[key] = None
        if state_cache[key]:
            hashes.add(state_cache[key])
    if not key and not hashes:
        return False
    excluded_states.update(hashes)
    for sha in hashes:
        all_sources_by_sha[sha][path] += 1
        if key:
            all_tuples_by_sha[sha].add(key)
    for sha in hashes & set(prior_by_sha):
        removals[sha].append({'source': path, 'case': label, 'reason': 'explicit_registered_or_recorded_state',
                              'episode': episode, 'saved_state_sha256': state_hash})
    if key in prior_by_tuple:
        sha = prior_by_tuple[key]['state_sha256']
        excluded_states.add(sha)
        if sha not in hashes:
            removals[sha].append({'source': path, 'case': label, 'reason': 'explicit_tuple_exclusion', 'episode': episode})
    return True


REF_KEYS = {'manifest', 'original_manifest', 'exclusion_manifests', 'explicit_exclusions', 'exclusion_inputs',
            'manifests', 'execution_manifests', 'ledger_inputs', 'declared_explicit_state_exclusions',
            'expert_timing_ledgers', 'ledger_files', 'ledgers', 'ledger', 'episodes', 'old_failure',
            'reserved_sources', 'reserved_manifests', 'input_files', 'files', 'runs', 'visits',
            'per_part_case_infrastructure_events'}


def follow(value, origin, context=None):
    if isinstance(value, list):
        for x in value:
            follow(x, origin, context)
    elif isinstance(value, dict):
        if value.get('cohort') == 'development':
            if 'path' in value:
                skips.append({'path': value['path'], 'origin': origin, 'reason': 'development_child_not_read'})
            return
        if isinstance(value.get('path'), str):
            enqueue(value['path'], origin, value.get('sha256'), value.get('rows'))
        for k, v in value.items():
            if k in REF_KEYS or k in ('first4', 'jobs'):
                follow(v, origin, k)
            elif k == 'original_manifest' and isinstance(v,str):
                enqueue(v, origin)
    elif isinstance(value, str) and ('results/harness_v5/' in value):
        enqueue(value, origin)


for path,numbers in refs.items():
    enqueue(path, 'COORDINATION:' + ','.join(map(str,numbers)))
for d in baseline['exclusion_inputs']:
    enqueue(d['path'], 'baseline_v2', d['sha256'])
# These launchers are named literally in COORD. Resolve their literal BASE
# assignments, not directory contents, and pin each manifest against COORD SHA.
named_launchers = [
    ('runtime_launchers/run_v5_grasp464_clean_receipt.sbatch',
     '1301a42418f7bfdd3368cd58406747568367987706a63813ec455674cc0c4b3e',
     {'smoke.json':'258d6aaf71cefb96bbe6abaae7f8904e5e3ab312b4ee3fc61d15c44f735eca49'}),
    ('runtime_launchers/run_v5_grasp473_rim_smoke.sbatch',
     'a9ecd8658a1cb70c352e2836b07ba7c2eb84c5701b95e3da96a8aaa35af23c1b',
     {'smoke.json':'a973a75913040c4d7f011aa07dc02ae156a4afb9244cd10896969c02a5067c03'}),
    ('scripts/run_v5_skill506_measured_smoke.sbatch', None,
     {'fixtures_smoke.json':'4b41dd0ce72b7694a20d0e1c95f299ac1caab77ae5f798ae0e3893cc11c65c37',
      'place_smoke.json':'37d3eac254090f553b9854846b922b359e3f83118626e3c0d18fcb2561c672c1',
      'grasp_subtask_smoke.json':'4ec7550ae488c9a77d3cf52694a8ad4ce49a8624478fc14db3b583e145163b02'}),
    ('scripts/run_v5_skill511_json_repaired_smoke.sbatch', None,
     {'fixtures_smoke.json':'4b41dd0ce72b7694a20d0e1c95f299ac1caab77ae5f798ae0e3893cc11c65c37',
      'place_smoke.json':'37d3eac254090f553b9854846b922b359e3f83118626e3c0d18fcb2561c672c1',
      'grasp_subtask_smoke.json':'4ec7550ae488c9a77d3cf52694a8ad4ce49a8624478fc14db3b583e145163b02'})]
for relative, expected_launcher, manifests in named_launchers:
    launcher = ROOT / relative
    assert relative in raw.decode()
    actual_launcher = digest(launcher)
    if expected_launcher:
        assert actual_launcher == expected_launcher
    text = launcher.read_text()
    base = ROOT / re.search(r'BASE="\$ROOT/([^"]+)"', text)[1]
    resolutions = []
    for index, line in enumerate(text.splitlines(),1):
        for match in re.finditer(r'\$BASE/(preparation/[A-Za-z0-9_]+\.json)',line):
            path = base / match[1]
            expected = manifests[path.name]
            enqueue(path, f'named_launcher:{relative}:{index}', expected)
            resolutions.append({'path':str(path),'launcher_line':index,'expected_manifest_sha256':expected})
    launcher_inputs.append({'path':str(launcher),'sha256':actual_launcher,
        'expected_sha256':expected_launcher,'explicit_manifest_resolutions':resolutions})
for p in (ACCESS529, ESTIMATE540):
    enqueue(p, 'explicit_known_index', trusted_index=True)
extra = json.loads(EXTRA.read_text())
for document in extra['coordination_documents']:
    assert digest(document['path']) == document['sha256']
enqueue(EXTRA, 'exact_tracked_coordination_supplied_by_root', trusted_index=True)
monitor = json.loads(MONITOR.read_text())
for job_id,j in monitor['jobs'].items():
    if isinstance(j.get('manifest'),dict):
        enqueue(j['manifest']['path'], 'monitor_job'+job_id, j['manifest']['sha256'])
    for d in j.get('ledgers',[]):
        enqueue(d['episodes'], 'monitor_job'+job_id)
    if j.get('fixed_final_report') and job_id in ('4148','4149'):
        # These explicit report indexes contain the original and resume manifests and ledgers.
        enqueue(j['fixed_final_report'], 'monitor_job'+job_id, j.get('report_sha256'), trusted_index=True)

while queue:
    path = queue.popleft()
    if path in loaded:
        continue
    loaded.add(path)
    d = descriptors[path]
    p = Path(path)
    if not p.is_file():
        d.update(exists=False, state_exclusions_complete=False)
        missing.append({'path': path, 'references': d['references']})
        continue
    data = p.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    d.update(exists=True, sha256=actual, bytes=len(data))
    expected = {x['expected_sha256'] for x in d['references'] if x['expected_sha256']}
    d['expected_sha256_matches_at_read'] = actual in expected if expected else None
    count = 0
    if path.endswith('episodes.jsonl'):
        ledger_lines = data.splitlines(keepends=True)
        d['rows'] = len([x for x in ledger_lines if x.strip()])
        d['historical_prefix_checks'] = []
        for x in d['references']:
            if x['expected_rows'] is not None and x['expected_sha256']:
                prefix = b''.join(ledger_lines[:x['expected_rows']])
                d['historical_prefix_checks'].append({'expected_rows':x['expected_rows'],
                    'expected_sha256':x['expected_sha256'], 'same_registered_prefix':hashlib.sha256(prefix).hexdigest()==x['expected_sha256']})
        for index, line in enumerate(ledger_lines, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                case_gaps.append({'source':path, 'line':index, 'reason':'nonclosed_jsonl_row'})
                continue
            case = row.get('case', row.get('episode', row))
            if not exclude(case, path, case.get('name', 'row'+str(index)) if isinstance(case,dict) else str(case)):
                d.setdefault('rows_without_original_state_identity', []).append(index)
            else:
                count += 1
    else:
        try:
            value = json.loads(data)
        except json.JSONDecodeError:
            case_gaps.append({'source':path, 'reason':'nonclosed_json_metadata'})
            continue
        if isinstance(value,dict):
            for field in ('cases','episodes'):
                entries = value.get(field,[])
                if not isinstance(entries,list):
                    continue
                for index, case in enumerate(entries):
                    if exclude(case, path, case.get('name', field+str(index)) if isinstance(case,dict) else str(case)):
                        count += 1
            follow(value,path)
        elif isinstance(value,list):
            for index, case in enumerate(value):
                if exclude(case,path,'entry'+str(index)):
                    count += 1
        d['metadata_has_state_cases'] = count > 0
    d['identified_original_cases_or_rows'] = count

# Some indexes add a second expected digest after an already read input.
for d in descriptors.values():
    expected = {x['expected_sha256'] for x in d['references'] if x['expected_sha256']}
    if d.get('exists'):
        d['expected_sha256_matches'] = d['sha256'] in expected if expected else None
        d['sha256_mismatches'] = sorted(expected - {d['sha256']})
sha_paths = defaultdict(list)
for p,d in descriptors.items():
    if d.get('sha256'):
        sha_paths[d['sha256']].append(p)
for context in sha_contexts:
    context['resolved_input_paths_by_sha'] = {h:sha_paths[h] for h in context['sha256s'] if h in sha_paths}
    context['unresolved_sha256s'] = [h for h in context['sha256s'] if h not in sha_paths]
unresolved_runtime_contexts = [x for x in sha_contexts if not x['resolved_input_paths_by_sha']
    and re.search(r'grasp|fixture|skill|stove|place|runtime', x['heading'] + ' ' + x['context'], re.I)
    and re.search(r'原版|original|libero|[0-9]+\s*(?:case|物理|请求)', x['heading'] + ' ' + x['context'], re.I)
    and not re.search(r'\b(?:CPU|scoring|training|capacity|render|media)\b', x['heading'], re.I)]
remaining = [r for r in prior if r['state_sha256'] not in excluded_states and
             (r['episode']['suite'],r['episode']['task'],r['episode']['seed']) not in excluded_tuples]
newly_excluded = [{'candidate':prior_by_sha[h], 'sources':sources} for h,sources in sorted(removals.items())]
report = {'scope':'Original90 pan upper bound after current explicit COORD, 529 raw ledgers, 540 indexes and monitor manifests',
    'producer_sha256':digest(__file__), 'coordination':coord_descriptor,
    'baseline_v2':{'path':str(BASELINE),'sha256':digest(BASELINE)},
    'prior_eligible_upper_bound':len(prior), 'prior_all_pan_presence_tuples':baseline['candidate_scene_tuples'],
    'explicit_input_count':len(descriptors), 'explicit_inputs_missing':missing,
    'input_read_counts':dict(Counter('ledger' if p.endswith('episodes.jsonl') else 'metadata' for p,d in descriptors.items() if d.get('exists'))),
    'named_launcher_reference_resolution_inputs':launcher_inputs,
    'input_sha_mismatches':[{'path':p,'actual':d['sha256'],'expected':d['sha256_mismatches']} for p,d in descriptors.items() if d.get('sha256_mismatches')],
    'original_scene_tuple_exclusion_count':len(excluded_tuples),
    'original_raw_state_exclusion_count':len(excluded_states),
    'newly_excluded_candidate_count':len(newly_excluded), 'newly_excluded_cases':newly_excluded,
    'eligible_upper_bound_after_explicit_audit':len(remaining),
    'eligible_unique_raw_states':len({r['state_sha256'] for r in remaining}),
    'eligible_by_task':dict(Counter(r['episode']['task'] for r in remaining)), 'eligible_cases':remaining,
    'identity_gaps':case_gaps, 'unresolved_path_templates':unresolved_paths,
    'manifest_sha_context_resolution':sha_contexts,
    'unresolved_original_runtime_registration_contexts':unresolved_runtime_contexts,
    'unknown_metadata_from_540':json.loads(ESTIMATE540.read_text())['unknown_exclusion_metadata'],
    'known_unresolved_reservation_aliases':extra['known_unresolved_reservation_aliases'],
    'exact_tracked_coordination_documents':extra['coordination_documents'],
    'sealed_metadata_scope_audit':extra['sealed_scope_evidence'],
    'complete_all_history_fresh_audit':False, 'upstream540_sealed_range_metadata_complete':False,
    'all_selection_confirmation_registry_complete':False,
    'scope_limit':'All explicit paths are considered. One prepared manifest alias and unpublished registrations remain unclosed. The 540 sealed flag has no supplied LIBERO-specific range and is not made a confirmation gate. Remaining pool is an upper bound.',
    'catalog_reads_count_as_visits':False, 'registered_unexecuted_cases_also_excluded':True,
    'ledger_row_presence_alone_does_not_certify_physics':True,
    'actual_confirmation_threshold':{'minimum_first_attempts_per_class':100, 'unique100_requirement_added':False,
       'selection_state_overlap_allowed':False, 'registered_repeat_identity_required':True,
       'unique_states_and_cluster_dependence_reported_separately':True},
    'qualification_authorized':False, 'new_physics':0, 'new_model_calls':0, 'new_training_rows':0,
    'no_glob_scandir':True,'no_sealed_payload_read':True,'no_PRO_read':True,'manual_or_training_files_read':False}
(OUT / 'explicit_access_input_index.json').write_text(json.dumps({'coordination':coord_descriptor,
    'inputs':list(descriptors.values()), 'named_launcher_inputs':launcher_inputs,
    'skipped_references':skips},indent=2)+'\n')
(OUT / 'explicit_original_state_exclusions.json').write_text(json.dumps({
    'scope':'Known registered states and recorded rows, with original tuple aliases; not a physical success label',
    'source_index':'explicit_access_input_index.json',
    'state_hash_encoding':'C contiguous little endian float64',
    'states':[{'state_sha256':sha,
       'original_scene_tuples':[dict(zip(('suite','task','seed'),key)) for key in sorted(all_tuples_by_sha[sha])],
       'explicit_source_row_or_registration_counts':dict(all_sources_by_sha[sha])}
       for sha in sorted(excluded_states)],
    'complete_all_history_fresh_audit':False},indent=2)+'\n')
(OUT / 'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('explicit_input_count','input_read_counts','newly_excluded_candidate_count',
    'eligible_upper_bound_after_explicit_audit','eligible_unique_raw_states','eligible_by_task')}))
print(json.dumps({'report_sha256':digest(OUT/'report.json'), 'missing':len(missing),
    'sha_mismatches':len(report['input_sha_mismatches']), 'identity_gaps':len(case_gaps)}))
