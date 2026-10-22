"""Return only new measurements for the frozen A queries, never B contexts."""
import argparse
from collections import Counter
import json
from pathlib import Path

from rpent.skill_package.contract import action_binding_required, method_family
from scripts.evaluate_bounded_saved_candidate import checked, digest
from coordination.bounded_skills_20261016.scripts.export_original_schema6_measured_CPU_20261021 import invocation_prompt, reference


def measured_row(query, report, policy_revision):
    """Keep one queried candidate's three repeats under its exact old binding."""
    if report['binding'] != query['binding'] or report['query_id'] != query['query_id']:
        raise ValueError('query context changed')
    public = query['public_request']
    if digest(public) != query['binding']['request_sha256']:
        raise ValueError('public request changed')
    candidate = next(c for c in public['candidates'] if c['id'] == query['candidate_id'])
    if candidate != query['candidate'] or report['candidate'] != candidate:
        raise ValueError('queried candidate changed')
    cid = candidate['id']
    family = method_family(candidate)
    required = action_binding_required(candidate)
    known_anchors = {a['id'] for a in public['anchors']}
    resolved = all(candidate['parameters'][k] in known_anchors
        for k in ('anchor_id', 'target_id') if k in candidate['parameters'])
    binding_status = 'resolved' if required and resolved else 'missing' if required else 'not_applicable'
    entries, unknown, seen = [], [], set()
    for item in report['trials']:
        trial = item['result']
        path = checked(item['summary'])
        if json.loads(path.read_bytes()) != trial:
            raise ValueError('raw trial changed')
        if (trial['binding'] != query['binding'] or trial['query_id'] != query['query_id']
                or trial['candidate_id'] != cid or trial['candidate_parameters'] != candidate['parameters']
                or trial['source_revision'] != query['binding']['source_revision']):
            raise ValueError('trial does not measure this frozen candidate')
        if trial['seed'] in seen:
            raise ValueError('duplicate noise seed')
        seen.add(trial['seed'])
        choices = [json.loads(line) for line in (path.parent/'choices.jsonl').read_text().splitlines()]
        if not choices:
            unknown.append({'seed': trial['seed'], 'reason': 'candidate_not_attempted', 'evidence': item['summary']})
            continue
        if choices and (digest(choices[0]['request']) != digest(public)
                or choices[0]['decision']['candidate_ids'] != [cid]):
            raise ValueError('first physical action differs from selected option')
        executions = [detail['execution'] for row in choices
            for detail in row.get('execution_details', [])
            if detail.get('candidate_id') == cid and 'execution' in detail]
        prompts, prompt_issue = invocation_prompt(trial['vla_inputs'], executions)
        if prompt_issue:
            unknown.append({'seed': trial['seed'], 'reason': prompt_issue, 'evidence': item['summary']})
            continue
        entry = {'sample_id': query['query_id']+'/'+str(trial['seed']), 'seed': trial['seed'],
            'status': trial['status'], 'success': trial['success'], 'reason': trial['reason'],
            'sim_steps': trial['sim_steps'], 'wall_s': trial['wall_s'],
            'private_metrology_s': trial['private_metrology_s'],
            'wall_scope': 'runtime excludes private post-branch metrology',
            'state_binding_verified': True, 'context_sha256': digest(query['binding']),
            'action_binding_status': binding_status, 'evidence': item['summary'],
            'invocation_evidence': item['summary']}
        if family == 'vla':
            import hashlib
            entry['effective_prompt_sha256'] = hashlib.sha256(prompts[0].encode()).hexdigest() if trial['vla_inputs'] else None
            entry['prompt_wire_status'] = 'observed' if trial['vla_inputs'] else 'not_invoked'
        entries.append(entry)
    if len(seen) != query['requested_valid_repeats']:
        raise ValueError('query repeats are not all closed')
    branch = {'candidate_id': cid, 'method_family': family,
        'action_binding_requirement': 'required' if required else 'not_required', 'trials': entries}
    if family == 'vla':
        branch['policy_revision'] = policy_revision
    return {'version': 'measured-subtask-choice/2', 'query_id': query['query_id'],
        'record_id': query['record_id'], 'record_aliases': query['record_aliases'],
        'public_request': public, 'prefix': query['prefix'], 'binding': query['binding'],
        'outcome_contract': query['outcome_contract'], 'snapshot': query['snapshot'],
        'branches': [branch], 'unknown_trials': unknown,
        'case': report['case'], 'source_episode_id': query['source_episode_id'],
        'PRO': False, 'D2': False, 'confirmation': False, 'training_admission': False,
        'evaluation_only': True, 'source_split': query['split'],
        'label_merge_scope': 'A exact binding only; supplement this candidate, never replace context or copy B outcomes',
        'raw_attempts': report['trials']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--policy-hashes', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.manifest.read_bytes())
    checked(plan['queries'])
    hashes = {Path(name).name: sha for sha, name in
        (line.split(maxsplit=1) for line in args.policy_hashes.read_text().splitlines())}
    assert set(hashes) == {'model.safetensors', 'metadata.pt'}
    policy_revision = 'pi05-libero-sha256:'+digest(hashes)
    rows = []
    for index, job in enumerate(plan['jobs']):
        pointer = json.loads((args.results/f'closed_{index:03d}.json').read_bytes())
        summary = {'path': pointer['summary'], 'sha256': pointer['sha256']}
        report = json.loads(checked(summary).read_bytes())
        row = measured_row(job['query'], report, policy_revision)
        row['source'] = summary
        rows.append(row)
    args.output.mkdir(parents=True, exist_ok=False)
    data = args.output/'positions.jsonl'
    data.write_text(''.join(json.dumps(row, sort_keys=True, ensure_ascii=False)+'\n' for row in rows))
    manifest = {'version': 'measured-subtask-choice/2', 'data': reference(data),
        'positions': len(rows), 'raw_trials': sum(len(row['raw_attempts']) for row in rows),
        'bound_trials': sum(len(b['trials']) for row in rows for b in row['branches']),
        'unknown_trials': sum(len(row['unknown_trials']) for row in rows),
        'by_category': dict(Counter(row['case']['category'] for row in rows)),
        'queries': plan['queries'], 'measurement_manifest': reference(args.manifest),
        'policy_hashes': hashes, 'policy_revision': policy_revision,
        'PRO': False, 'D2': False, 'confirmation': False, 'training_admission': False,
        'evaluation_only': True, 'scope': 'new queried-candidate outcomes only; comparison labels require exact-binding merge with original A packet'}
    (args.output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(manifest), flush=True)


if __name__ == '__main__':
    main()
