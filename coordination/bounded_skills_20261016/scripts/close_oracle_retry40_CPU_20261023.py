"""Close the revised recovery-one diagnostic without rerunning closed cases."""
import json
from pathlib import Path
import subprocess
import sys


def main():
    root = Path('/public/home/sunyihan/rpent_libero_eval')
    base = root/'results/bounded_skills/execution_repairs_20261022'
    run = base/'option_ceiling_20261022'
    output = run/'oracle_retry_fb9b3865/CPU_closed40'
    subprocess.run([sys.executable, str(run/'aggregate_B2_D2_CPU_20261021.py'),
        '--root', str(output.parent), '--budgets', '1', '--shards', '0', '1',
        '--a1', str(base/'D2_preparation_c6b62442/preparation/A1_M_40_reference.json'),
        '--output', str(output)], check=True)
    current = [json.loads(line) for line in (output/'paired_cases.jsonl').read_text().splitlines()]
    old = {row['case']: row for row in map(json.loads,
        (base/'D2_option_fallback_a3c7cf43/CPU_closed120_selected_paths/aggregate/paired_cases.jsonl').read_text().splitlines())
        if row['recovery_budget'] == 1}
    model = {row['case']: row for row in map(json.loads,
        (run/'CPU_model40_closed_r1/paired_cases.jsonl').read_text().splitlines())}
    assert len(current) == len(old) == len(model) == 40
    rows = []
    table = ['| 局 | 新oracle回放 | 新采样上限 | 旧oracle回放 | 旧采样上限 | 模型 | A1-M |',
        '|---|---:|---:|---:|---:|---:|---:|']
    def display(value):
        return '?' if value is None else str(int(value))
    for row in current:
        name = row['case']
        row.update(old_oracle_success=old[name]['success'],
            old_sampled_success=old[name]['sampled_envelope_success'],
            model_success=model[name]['model_success'])
        rows.append(row)
        table.append('| '+name+' | '+' | '.join(display(row[k]) for k in
            ('success', 'sampled_envelope_success', 'old_oracle_success', 'old_sampled_success',
             'model_success', 'A1_M_success'))+' |')
    (output/'comparison.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
    (output/'comparison.md').write_text('\n'.join(table)+'\n\n同任务/初态编号协议；各历史臂的完整物理初态未认证为相同，不作因果选择错误归因。\n')
    print(json.dumps({'output': str(output), 'closed': len(rows),
        'replay_success': sum(row['success'] for row in rows),
        'sampled_success': sum(row['sampled_envelope_success'] is True for row in rows),
        'unknown': sum(row['sampled_envelope_success'] is None for row in rows)}), flush=True)


if __name__ == '__main__':
    main()
