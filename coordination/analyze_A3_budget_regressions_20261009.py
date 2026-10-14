"""Separate step spending, macro availability and runtime source binding."""

from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
CURRENT = ROOT / 'artifacts/skill_budget_A3N80_complete_20261009_r1'
BASELINE = ROOT / 'artifacts/fulltask_A3N80_20261009_closed_r1'
OUTPUT = ROOT / 'artifacts/A3_regressions_and_spatial_binding_20261009_r1'


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def identity(row):
    e = row['episode']
    return e['suite'], e['task'], e['seed']


def trace_path(row):
    if 'trace' in row:
        v = row['trace']
        if 'choices' in v:
            return Path(v['choices']['path'])
        if 'path' in v:
            return Path(v['path'])
    return Path(row['output_dir']) / 'choices.jsonl'


def analyze(row):
    p = trace_path(row)
    trace = rows(p)
    history, macro, reasons, steps, instructions = [], [], Counter(), Counter(), set()
    for event in trace:
        r = event.get('receipt') or {}
        tool = r.get('tool')
        context = event['request']['context']
        instructions.update(line for line in context.splitlines() if line.startswith('instruction '))
        options = event.get('candidates', [])
        available = 'vla_task()' in options
        blocked = [line for line in context.splitlines() if line.startswith('blocked vla_task()')]
        step = r.get('sim_steps_used')
        if step is not None:
            steps[tool] += step
        reasons[str(r.get('failure_reason') or r.get('verification'))] += 1
        entry = {'decision': event['decision'], 'selected': event['selected'],
                 'verification': r.get('verification'), 'failure_reason': r.get('failure_reason'),
                 'sim_steps': step, 'remaining_before': event.get('execution_budget_before'),
                 'remaining_after': event.get('execution_budget_after'),
                 'vla_task_offered': available, 'vla_task_blocked_lines': blocked,
                 'official_success': event.get('official_success'),
                 'contact_prompt': r.get('contact_prompt') or r.get('subtask_prompt')}
        if tool == 'vla_task':
            macro.append(entry)
        history.append(entry)
    first_failure = next((e['decision'] for e in macro
                          if e['official_success'] is False), None)
    tail = [e for e in history if first_failure is not None and e['decision'] > first_failure]
    return {'choices': ref(p), 'instruction_lines': sorted(instructions),
            'skill_steps': dict(steps), 'macro_attempts': macro,
            'after_first_macro_failure': {'decisions': len(tail),
                'offered': sum(e['vla_task_offered'] for e in tail),
                'blocked': sum(bool(e['vla_task_blocked_lines']) for e in tail)},
            'receipt_reasons': dict(reasons), 'history': history}


def main():
    current = {identity(r): r for r in rows(CURRENT / 'episodes.jsonl')}
    baseline = {identity(r): r for r in rows(BASELINE / 'episodes.jsonl')}
    paired = rows(CURRENT / 'paired.jsonl')
    selected = [r for r in paired if (r['baseline_success'] and not r['current_success'])
                or r['episode']['suite'] == 'libero_spatial_task']
    output = []
    for pair in selected:
        key = identity(pair)
        new, old = analyze(current[key]), analyze(baseline[key])
        output.append({'episode': pair['episode'], 'regression': pair['baseline_success']
                       and not pair['current_success'], 'baseline_success': pair['baseline_success'],
                       'current_success': pair['current_success'], 'current': new, 'baseline': old,
                       'retry_causality': 'not identifiable from different reached states; matched-prefix replay needed'})
    OUTPUT.mkdir(exist_ok=False)
    ledger = OUTPUT / 'episode_diagnoses.jsonl'
    ledger.write_text(''.join(json.dumps(r) + '\n' for r in output))
    table = ['| suite/task/init | old/new | steps by skill | macro attempts old/new | post-failure offered/blocked |',
             '|---|---|---|---|---|']
    for r in output:
        e=r['episode']; new=r['current'];tail=new['after_first_macro_failure']
        table.append(f"| {e['suite']}/{e['task']}/{e['seed']} | {int(r['baseline_success'])}/{int(r['current_success'])} | "
                     + ', '.join(f'{k}:{v}' for k,v in sorted(new['skill_steps'].items()))
                     + f" | {len(r['baseline']['macro_attempts'])}/{len(new['macro_attempts'])} | {tail['offered']}/{tail['blocked']} |")
    (OUTPUT / 'REPORT.md').write_text('\n'.join(table) + '\n\nDifferent reached states do not establish that masking caused a lost successful retry.\n')
    manifest = {'records': ref(ledger), 'inputs': [ref(CURRENT / 'episodes.jsonl'),
                ref(BASELINE / 'episodes.jsonl'), ref(CURRENT / 'paired.jsonl')],
                'source': ref(Path(__file__)), 'regression_count':sum(r['regression'] for r in output),
                'spatial_task_count':sum(r['episode']['suite']=='libero_spatial_task' for r in output),
                'new_model_calls':0, 'new_physics_runs':0, 'training_allowed':False}
    p=OUTPUT / 'manifest.json';p.write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'manifest':ref(p),'records':len(output)}))
    print('\n'.join(table))


if __name__ == '__main__':
    main()
