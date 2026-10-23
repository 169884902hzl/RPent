"""Describe measured preparation failures without changing any recorded score."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path


def reference(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def wilson(k, n):
    if not n:
        return None
    z = 1.959963984540054
    d = 1+z*z/n
    centre = (k/n+z*z/(2*n))/d
    half = z*math.sqrt(k*(n-k)/n**3+z*z/(4*n*n))/d
    return [max(0., centre-half), min(1., centre+half)]


def counts(rows, field):
    known = [r[field] for r in rows if type(r[field]) is bool]
    k = sum(known)
    return {'trials': len(rows), 'known': len(known), 'success': k,
        'unknown': len(rows)-len(known), 'wilson95_over_repeats': wilson(k, len(known))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    parent = args.run/'CPU_155'
    summary = json.loads((parent/'summary.json').read_bytes())
    panel = json.loads((args.run/'preparation/all155.json').read_bytes())
    cases = {j['case']['name']: j['case'] for j in panel['jobs']}
    assert len(cases) == 155 and panel['training'] is False
    paired = [json.loads(line) for line in (parent/'paired_trials.jsonl').read_text().splitlines()]
    added = [json.loads(line) for line in (parent/'added_trials.jsonl').read_text().splitlines()]
    assert len(paired) == 1165 and len(added) == 465
    cache, output = {}, []
    for row in added:
        name = row['case']
        case = cases[name]
        assert case['diagnostic']['domain'] == 'original'
        if name not in cache:
            path = Path(row['after']['path'])
            assert reference(path) == row['after']
            cache[name] = json.loads(path.read_bytes())
        trial = next(t for t in cache[name]['trials'] if t['method'] == 'call_vla'
            and t['vla_variant']['name'] == 'measured_anchor' and t['trial_seed'] == row['seed'])
        assert trial['success'] == row['after_success']
        assert trial['native_task_success'] == row['after_native_success']
        preparations = []
        if row['after_reason'] == 'preparation_not_reached':
            choices = Path(trial['choices']['path'])
            assert reference(choices) == trial['choices']
            for line in choices.read_text().splitlines():
                choice = json.loads(line)
                for detail in choice.get('execution_details', []):
                    prep = detail.get('execution', {}).get('preparation')
                    if not prep or prep.get('mode') != 'measured_anchor':
                        continue
                    component = prep['component']
                    receipt = component.get('receipt', {})
                    preparations.append({'decision': choice['index'], 'skill': component['skill'],
                        'success': component['success'], 'reason': component['reason'],
                        'phase': receipt.get('phase'), 'steps_used': component['steps_used']})
        failed = [p for p in preparations if not p['success']]
        output.append({**row, 'domain': case['comparison_domain'],
            'source_public_id': trial['source_public_id'], 'target_public_id': trial['target_public_id'],
            'selected_candidate_id': trial['selected_candidate_id'],
            'actual_selected_vla_variants': trial['executed_vla_variants'],
            'vla_inference_calls': trial['vla_inference_calls'], 'preparation_events': preparations,
            'last_preparation_failure': failed[-1]['reason'] if failed else None,
            'choices': trial['choices'], 'training': False})
    groups = defaultdict(list)
    for row in output:
        groups[(row['domain'], row['category'])].append(row)
    failed = [r for r in output if r['after_success'] is False]
    args.output.mkdir(parents=True, exist_ok=False)
    data = args.output/'trials.jsonl'
    data.write_text(''.join(json.dumps(r, sort_keys=True)+'\n' for r in output))
    report = {'source_commit': panel['source_commit'], 'source_registration': reference(args.run/'registration.json'),
        'parent': reference(parent/'summary.json'), 'data': reference(data),
        'states': len(cases), 'domain_states': dict(Counter(c['comparison_domain'] for c in cases.values())),
        'legacy_selected_id_changes': sum(not r['same_candidate_id'] for r in paired),
        'legacy_improvements': [r for r in paired if r['improved']],
        'legacy_regressions': [r for r in paired if r['regressed']],
        'new_local': counts(output, 'after_success'), 'new_native': counts(output, 'after_native_success'),
        'new_failed_stop_reasons': dict(Counter(r['after_reason'] for r in failed)),
        'new_failed_preparation_inner_reasons': dict(Counter(r['last_preparation_failure']
            for r in failed if r['after_reason'] == 'preparation_not_reached')),
        'selected_without_policy_inference': sum(not r['vla_inference_calls'] for r in output),
        'by_domain_category': [{'domain': key[0], 'category': key[1],
            'local': counts(group, 'after_success'), 'native': counts(group, 'after_native_success')}
            for key, group in sorted(groups.items())],
        'training': False, 'PRO': False, 'D2': False, 'confirmation': False,
        'scope': 'read-only original/own-layout audit. Inner collision/IK records are screening results, not private physical collision truth. Local subtask, native whole task, stop reason and inference invocation remain separate; repeated trials are not independent layouts.'}
    (args.output/'manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k: report[k] for k in ('states', 'legacy_selected_id_changes', 'new_local',
        'new_native', 'new_failed_stop_reasons', 'new_failed_preparation_inner_reasons')}), flush=True)


if __name__ == '__main__':
    main()
