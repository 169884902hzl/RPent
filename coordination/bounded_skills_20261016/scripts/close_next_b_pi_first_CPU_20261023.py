"""Summarize retained closed cases; pending/interface errors are never failures."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def read_ref(item):
    path = Path(item.get('summary', item.get('path')))
    assert hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256'], path
    return json.loads(path.read_text()), ref(path)


def rows(path):
    return [json.loads(s) for s in path.read_text().splitlines()]


def score(values):
    known = [v for v in values if v is not None]
    n = len(known)
    s = sum(known)
    if not n:
        return {'success': 0, 'n': 0, 'unknown_or_pending': len(values), 'wilson95': None}
    z = 1.959963984540054
    c = (s/n+z*z/(2*n))/(1+z*z/n)
    h = z*math.sqrt(s/n*(1-s/n)/n+z*z/(4*n*n))/(1+z*z/n)
    return {'success': s, 'n': n, 'unknown_or_pending': len(values)-n,
            'wilson95': [max(0, c-h), min(1, c+h)]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--allow-incomplete', action='store_true')
    a = p.parse_args()
    run = a.root/'results/bounded_skills/next_b_pi_first_20261023'
    base = a.root/'results/bounded_skills/execution_repairs_20261022/option_ceiling_20261022'
    pi_path = a.root/'results/bounded_skills/pi_only_and_approach_20261023/CPU_pi_only46/episodes.jsonl'
    pi = {r['arm_id']: r for r in rows(pi_path)}
    old_model = {r['case']: r for r in rows(base/'CPU_model40_closed_r1/paired_cases.jsonl')}
    old_oracle = {r['case']: r for r in rows(base/'measured_anchor_2db20013/CPU_closed40/comparison.jsonl')}
    model = {}
    pending = []
    for stage in ['model_d2_0', 'model_d2_1', 'model_d2_2', 'model_original6']:
        plan = json.loads((run/f'preparation/{stage}_capacity256.json').read_text())
        for i, job in enumerate(plan['jobs']):
            key = job['case']['name'] + (f"_K{job['k']}" if stage == 'model_original6' else '')
            pointer = run/stage/f'closed_{i:03d}.json'
            if not pointer.is_file():
                pending.append({'stage': stage, 'case': key})
                continue
            data, raw = read_ref(json.loads(pointer.read_text()))
            assert data['status'] == 'physical_result' and data['case'] == job['case']
            assert data['human_available'] is False and data['oracle_choices_used'] == 0
            assert data['initial_snapshot']['physics_sha256'] == pi[key]['initial_physics_sha256']
            assert data['registered_initial_restoration']['complete_physics_matches']
            requests = rows(Path(raw['path']).parent/'episode/requests.jsonl')
            assert all(r['request']['human_available'] is False for r in requests)
            model[key] = {k: data[k] for k in ('success', 'decisions', 'sim_steps', 'stop_reason',
                'recovery_used', 'wall_s', 'wall_time_breakdown', 'skill_sim_steps', 'source_commit', 'initial_snapshot')}
            model[key].update(raw=raw, model_service=data['model_service'], requests_with_human_false=len(requests))
    endpoints, endpoints_ref = read_ref(ref(run/'preparation/pi_first_endpoints.json'))
    endpoints = {r['case']: r for r in endpoints['reproductions']}
    recovered = {}
    for stage in [f'pi_first_oracle_origin_{i}' for i in range(4)]:
        plan = json.loads((run/f'preparation/{stage}.json').read_text())
        for i, job in enumerate(plan['jobs']):
            key = job['case']['name']
            pointer = run/stage/f'closed_{i:03d}.json'
            if not pointer.is_file():
                pending.append({'stage': stage, 'case': key})
                continue
            data, raw = read_ref(json.loads(pointer.read_text()))
            assert data['case'] == job['case'] and 'actual_full_replay_success' in data
            assert endpoints[key]['complete_retained_endpoint_matches']
            attempts = rows(Path(pi[key]['attempt_records']['path']))
            first = attempts[0]
            # The endpoint SHA comes from a matching retained control replay or
            # a verified same-seed first attempt, never a later retry endpoint.
            endpoint_evidence, _ = read_ref(endpoints[key]['source_result'])
            assert endpoint_evidence['retained_endpoint_matches']
            replay = data['full_replay']
            assert replay, 'closed continuation must include an actual native replay'
            recovered[key] = {
                'success': data['actual_full_replay_success'],
                'sampled_success': data.get('sampled_envelope_native_success'),
                'status': data['status'], 'raw': raw,
                'unsupported': data.get('unsupported', []),
                'first_attempt': {k: v for k, v in first.items()
                    if k in ('stop_reason', 'final_physics_sha256', 'initial_physics_sha256',
                        'actual_sim_steps', 'vla_inference_calls', 'native_success', 'sampling_seed', 'budget')},
                'first_endpoint': endpoints[key],
                'replay_sim_steps': sum(t['sim_steps'] for t in replay),
                'replay_decisions': sum(t['decisions'] for t in replay),
                'replay_vla_inference_calls': sum(t['vla_inference_calls'] for t in replay),
                'independent_replay_wall_s': data['independent_replay_wall_s'],
                'replay_stop_reasons': [t['reason'] for t in replay],
                'replay_initial_physics_sha256': replay[0].get('initial_physics_sha256'),
                'episode_initial_checkpoint': ref(Path(raw['path']).parent/'episode/private_initial.pkl'),
                'path_selection': data.get('path_selection'),
                'source_commit': data['source_commit'],
                'endpoint_reconstruction_evidence': endpoints[key]['source_result'],
            }
    if not a.allow_incomplete:
        assert not pending, pending
        assert len(model) == 46 and len(recovered) == 24
    comparisons = []
    for key in sorted(k for k, v in pi.items() if v['domain'] == 'd2'):
        prior = pi[key]
        first_success = prior['first_attempt_success']
        continuation = recovered.get(key)
        mixed = True if first_success else continuation['success'] if continuation else None
        upper = True if first_success else continuation['sampled_success'] if continuation else None
        comparisons.append({'case': key, 'suite': prior['case']['episode']['suite'],
            'pi_only_success': prior['success'], 'pi_first_success': first_success,
            'v_next_a_success': old_model[key]['model_success'],
            'v_next_b_success': model.get(key, {}).get('success'),
            'oracle_from_start_success': old_oracle[key]['success'],
            'A1_M_success': old_oracle[key]['A1_M_success'],
            'pi_then_oracle_replay_success': mixed, 'pi_then_oracle_sampled_success': upper,
            'initial_physics_sha256': prior['initial_physics_sha256'],
            'model_complete_initial_matches_pi': key in model,
            'model': model.get(key), 'pi_then_oracle': continuation,
            'pi_only_raw': prior['raw'], 'old_oracle_raw': old_oracle[key]['summary']})
    original = []
    for key in sorted(k for k, v in pi.items() if v['domain'] == 'original'):
        original.append({'arm_id': key, 'pi_only_success': pi[key]['success'],
            'v_next_b_success': model.get(key, {}).get('success'), 'model': model.get(key),
            'initial_physics_sha256': pi[key]['initial_physics_sha256']})
    keys = ('pi_only_success', 'v_next_a_success', 'v_next_b_success', 'oracle_from_start_success',
            'A1_M_success', 'pi_then_oracle_replay_success', 'pi_then_oracle_sampled_success')
    summary = {'D2': {k: score([r[k] for r in comparisons]) for k in keys},
        'first_failure24': {k: score([r[k] for r in comparisons if not r['pi_first_success']])
            for k in ('pi_then_oracle_replay_success', 'pi_then_oracle_sampled_success')},
        'original6': {k: score([r[k] for r in original]) for k in ('pi_only_success', 'v_next_b_success')},
        'model_closed': len(model), 'continuation_closed': len(recovered), 'pending': pending,
        'complete_model_initial_matches': len(model), 'human_available': False,
        'model_legal_version': 5, 'old_model_legal_version': 4,
        'comparison_caveat': 'not a weights-only comparison: legal4->5, schema6->7 human capability, additional codec capacity and 32k request allowance; failures before interface repair retained but not physical outcomes',
        'original6_scope': 'three distinct initial states, each run at inherited K1/K4 labels',
        'sampling_caveat': 'development finite-sample envelope with look-ahead branch selection, not an executable model result; unknown excluded and counted explicitly',
        'recovery_caveat': 'continuation recovery1 starts after one pi failure and may call pi more than one additional time; original total10000 simulation-step budget is retained, not reset; branch search costs excluded from replay latency',
        'pi_endpoint_reconstructions': dict(Counter(v['reconstruction'] for v in endpoints.values())),
        'sources': {'pi_only': ref(pi_path), 'pi_endpoints': endpoints_ref},
        'training': False, 'evaluation_only': True}
    for group in ('D2', 'first_failure24'):
        summary[group + '_scope'] = 'full registered cohort; missing/unknown shown separately'
    a.output.mkdir(parents=True, exist_ok=False)
    for name, values in [('paired_cases', comparisons), ('original6', original)]:
        (a.output/f'{name}.jsonl').write_text(''.join(json.dumps(r, sort_keys=True)+'\n' for r in values))
    (a.output/'manifest.json').write_text(json.dumps(summary, indent=2)+'\n')
    def cell(x): return '?' if x is None else str(int(x))
    table = ['| 场景 | 只用π | 旧模型 | 新模型 | 开局oracle | π后oracle回放 | π后采样 |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for r in comparisons:
        table.append('| '+r['case']+' | '+' | '.join(cell(r[k]) for k in
            ('pi_only_success', 'v_next_a_success', 'v_next_b_success', 'oracle_from_start_success',
             'pi_then_oracle_replay_success', 'pi_then_oracle_sampled_success'))+' |')
    (a.output/'paired_table.md').write_text('\n'.join(table)+'\n')
    print(json.dumps({k: v for k, v in summary.items() if k not in ('pending', 'sources')}))


if __name__ == '__main__':
    main()
