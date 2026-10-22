"""Close the frozen model cohort and notify its service owner immediately."""
from collections import Counter
import datetime
import hashlib
import json
import math
from pathlib import Path


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def wilson(k, n):
    z = 1.959963984540054
    c = (k/n+z*z/(2*n))/(1+z*z/n)
    h = z*math.sqrt(k*(n-k)/n**3+z*z/(4*n*n))/(1+z*z/n)
    return [c-h, c+h]


def closed(directory, count):
    result = []
    for index in range(count):
        pointer = json.loads((directory/f'closed_{index:03d}.json').read_bytes())
        path = Path(pointer['summary'])
        assert ref(path)['sha256'] == pointer['sha256']
        row = json.loads(path.read_bytes())
        assert row['status'] == 'physical_result' and row['oracle_choices_used'] == 0
        assert not row['training'] and not row['confirmation']
        result.append({'data': row, 'summary': ref(path)})
    return result


def main():
    root = Path('/public/home/sunyihan/rpent_libero_eval')
    base = root/'results/bounded_skills/execution_repairs_20261022'
    run = base/'option_ceiling_20261022'
    model = run/'native_model_7f87b8ef'
    original = closed(run/'native_model_09e37883/model_original6', 6)
    d2 = closed(model/'model_D2_recovery1', 40)
    plan = json.loads((model/'preparation/model_D2_recovery1.json').read_bytes())
    assert [r['data']['case'] for r in d2] == [r['case'] for r in plan['jobs']]
    assert all(r['data']['domain'] == 'd2' and r['data']['recovery_budget'] == 1 for r in d2)
    a1_path = base/'D2_preparation_c6b62442/preparation/A1_M_40_reference.json'
    a1 = {r['case']: r['native_success'] for r in json.loads(a1_path.read_bytes())['episodes'] if r['group'] == 'A1-M'}
    old_path = base/'D2_option_fallback_a3c7cf43/CPU_closed120_selected_paths/aggregate/paired_cases.jsonl'
    old = {r['case']: r for r in map(json.loads, old_path.read_text().splitlines()) if r['recovery_budget'] == 1}
    assert len(a1) == len(old) == 40
    assert sum(r['success'] for r in old.values()) == 21
    assert sum(r['sampled_envelope_success'] is True for r in old.values()) == 24
    assert sum(r['sampled_envelope_success'] is None for r in old.values()) == 2
    pairs = []
    for item in d2:
        row = item['data']
        name = row['case']['name']
        pairs.append({'case': name, 'suite': row['case']['episode']['suite'],
            'model_success': row['success'], 'old_oracle_success': old[name]['success'],
            'old_sampled_success': old[name]['sampled_envelope_success'], 'A1_M_success': a1[name],
            'model_stop_reason': row['stop_reason'], 'model_decisions': row['decisions'],
            'model_sim_steps': row['sim_steps'], 'model_skill_sim_steps': row['skill_sim_steps'],
            'model_wall_s': row['wall_s'], 'model_initial_snapshot': row['initial_snapshot'],
            'raw': item['summary']})
    success = sum(r['model_success'] for r in pairs)
    out = run/'CPU_model40_closed_r1'
    out.mkdir(exist_ok=False)
    path = out/'paired_cases.jsonl'
    path.write_text(''.join(json.dumps(r)+'\n' for r in pairs))
    report = {'model': {'success': success, 'n': 40, 'wilson95': wilson(success, 40)},
        'old_oracle_replay': {'success': 21, 'n': 40, 'source': ref(old_path)},
        'old_sampled_upper_bound': {'success': 24, 'known': 38, 'unknown': 2, 'source': ref(old_path)},
        'A1_M': {'success': 28, 'n': 40, 'source': ref(a1_path)},
        'by_suite': {suite: {'n': 5, 'success': sum(r['model_success'] for r in pairs if r['suite'] == suite),
            'wilson95': wilson(sum(r['model_success'] for r in pairs if r['suite'] == suite), 5)}
            for suite in sorted({r['suite'] for r in pairs})},
        'original6': {'success': sum(r['data']['success'] for r in original), 'n': 6,
            'scope': 'three init identities at K1/K4; complete initial physics digests differ; not a strict K paired experiment',
            'rows': original},
        'model_source': sorted({r['data']['source_commit'] for r in d2}),
        'adapter_sha256': plan['model_service']['adapter_sha256'],
        'stop_reasons': dict(Counter(r['model_stop_reason'] for r in pairs)),
        'pairing_scope': 'same task/init protocol only; model initial complete-state hashes do not certify equality to the historical oracle/A1 arms; no causal selected-error count inferred',
        'recovery_scope': 'public held-state transitions/successful call_vla; historical oracle resets by its private subtask rules',
        'rows': ref(path), 'code_capacity_compatibility': ref(model/'service_codes120_compatibility_ready.json'),
        'training': False, 'PRO_training': False, 'confirmation_training': False}
    (out/'summary.json').write_text(json.dumps(report, indent=2)+'\n')
    table = ['| 局 | 模型 | 旧oracle回放 | 旧采样上限 | A1-M | 模型结束原因 |',
        '|---|---:|---:|---:|---:|---|']
    for row in pairs:
        sampled = '?' if row['old_sampled_success'] is None else int(row['old_sampled_success'])
        table.append(f"| {row['case']} | {int(row['model_success'])} | {int(row['old_oracle_success'])} | {sampled} | {int(row['A1_M_success'])} | {row['model_stop_reason']} |")
    (out/'paired_table.md').write_text('\n'.join(table)+'\n')
    notify = root/'coordination/owner_alerts/Codex2/C3_MODEL40_COMPLETE_STOP11532_20261023.json'
    notify.parent.mkdir(parents=True, exist_ok=True)
    notify.write_text(json.dumps({'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'model_D2': report['model'], 'original6': {'success': report['original6']['success'], 'n': 6},
        'complete': True, 'summary': ref(out/'summary.json'),
        'message': 'All forty model D2 and six original arms are closed. Please stop your service11532 now per user instruction. Frozen onpolicy75 physical measurements do not need the decision-model service. No training.'}, indent=2)+'\n')
    print(json.dumps({'output': str(out), 'model': report['model'], 'notified_C2_stop': str(notify)}), flush=True)


if __name__ == '__main__':
    main()
