"""Summarize the preserved original-task contact/refresh failure on CPU."""
import json
from pathlib import Path

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'results/bounded_skills/feasibility_20261017/job8843_80'
path = base/'drawer_close_libero_90_t0_s0_oracle_k4/choices.jsonl'
rows = []
for line in path.open():
    choice = json.loads(line)
    request = choice['request']
    candidates = {c['id']: c for c in request['candidates']}
    answer = choice.get('decision') or {}
    rows.append(dict(index=choice['index'], observation_id=request['observation_id'],
        selected=[{key: candidates[cid][key] for key in ('id', 'skill', 'parameters')}
            for cid in answer.get('candidate_ids', [])],
        safe_positive_y_nudges=[{key: c[key] for key in ('id', 'parameters')}
            for c in candidates.values() if c['skill'] == 'nudge'
            and c['parameters'].get('axis') == 'y' and c['parameters'].get('distance_m', 0.) > 0.
            and c['consequences']['collision'] is not True
            and c['consequences']['ik_reachable'] is not False],
        receipts=[{key: rec.get(key) for key in ('skill', 'candidate_id', 'outcome',
            'stop_reason', 'steps_used', 'expectation_checks')}
            for rec in choice.get('receipts', [])], error=choice.get('error')))
report = dict(source=str(path), job='8843_80', scope='preserved development failure, CPU log analysis',
    observation='Two successful nudges are followed by no-effect refreshes and a failed wrist scan.',
    hypothesis='The private oracle appends a refresh after a blocked speculative contact successor, although executor steps already measure receipts.',
    public_screens_relaxed=False, physical_repair_verified=False, rows=rows)
output = root/'coordination/bounded_skills_20261016/reports/drawer8843_prefix_observe_CPU_20261018.json'
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(dict(output=str(output), decisions=len(rows),
    receipts=[[(r['skill'], r['outcome'], r['stop_reason']) for r in row['receipts']] for row in rows],
    safe_nudges=[len(row['safe_positive_y_nudges']) for row in rows])))
