"""Report measured exclusive wall time, retaining uninstrumented residuals."""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, default=Path('/public/home/sunyihan/rpent_libero_eval'))
parser.add_argument('--job', action='append', required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
rows = []
for job in args.job:
    base = args.root/'results/bounded_skills/feasibility_20261017'
    directories = [base/('job'+job)] if '_' in job else sorted(base.glob('job'+job+'_*'))
    for directory in directories:
        ledger = directory/'episodes.jsonl'
        if not ledger.exists():
            continue
        for row in map(json.loads, ledger.read_text().splitlines()):
            if row.get('status') != 'physical_result':
                continue
            timing = row.get('wall_time_breakdown')
            entry = dict(job=directory.name, case=row['case']['name'], arm=row['arm'],
                success=row['success'], decisions=row['decisions'], sim_steps=row['sim_steps'],
                wall_s=row['wall_s'], raw_episode_ledger=str(ledger))
            if timing is None:
                path = directory/(row['case']['name']+'_'+row['arm'])/'choices.jsonl'
                request_s = sum(json.loads(line).get('request_generation_s', 0.)
                    for line in path.read_text().splitlines())
                entry.update(instrumented=False, measured_request_generation_s=request_s,
                    unseparated_residual_s=row['wall_s']-request_s)
            else:
                main = timing['main_thread_exclusive_s']
                def total(prefix):
                    return sum(value for key, value in main.items() if key.startswith(prefix))
                buckets = {key: total(prefix) for key, prefix in (
                    ('perception_s', 'perception.'), ('consequence_planning_s', 'planning.'),
                    ('simulation_step_render_s', 'simulation.'), ('oracle_decision_s', 'decision.oracle'),
                    ('model_decision_s', 'decision.model'), ('pi05_inference_s', 'vla.'),
                    ('artifact_io_s', 'artifact_io'), ('execution_other_s', 'execution.other'))}
                accounted = sum(buckets.values())
                assert abs(accounted-sum(main.values())) < 1e-6, 'an instrumented category is missing'
                residual = timing['main_thread_unattributed_s']
                assert accounted <= row['wall_s']+1e-3, 'overlapping main-thread times'
                execution = timing.get('main_thread_exclusive_by_root_s', {}).get('execution.other', {})
                entry.update(instrumented=True, **buckets, unattributed_s=residual,
                    perception_components_s={key: main.get('perception.'+key, 0.)
                        for key in ('segmentation', 'depth', 'entity_measurement', 'capture_io')},
                    execution_perception_s=sum(v for k, v in execution.items() if k.startswith('perception.')),
                    oracle_root_inclusive_s=sum(timing.get('main_thread_exclusive_by_root_s', {}).get('decision.oracle', {}).values()),
                    exclusive_detail_s=main,
                    all_threads_exclusive_s=timing['all_threads_exclusive_s'],
                    exclusive_by_root_s=timing.get('main_thread_exclusive_by_root_s'),
                    raw_spans=str(directory/(row['case']['name']+'_'+row['arm'])/'wall_time_spans.json'))
            rows.append(entry)
report = dict(rows=rows, scope='Per-episode client wall time; initial simulator construction excluded',
    additive='Only main-thread exclusive buckets plus residual can be summed to wall_s.',
    worker_overlap='All-thread totals may overlap main-thread wall time; never add them to it.',
    history='No detailed category is backfilled into historical uninstrumented results.',
    oracle='oracle_decision_s is exclusive selector work; oracle_root_inclusive_s also includes its nested planning and is not additive.',
    training=False, confirmation=False)
args.output.write_text(json.dumps(report, indent=2)+'\n')
lines = ['| Job / state / arm | Success | Wall s | Perception | Plan | Sim/render | Oracle exclusive | pi05 | Other + IO | Residual |',
    '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
for row in rows:
    values = [f"{row['job']} / {row['case']} / {row['arm']}", str(row['success']), f"{row['wall_s']:.3f}"]
    if row['instrumented']:
        values += [f"{row[k]:.3f}" for k in ('perception_s', 'consequence_planning_s',
            'simulation_step_render_s', 'oracle_decision_s', 'pi05_inference_s')]
        values += [f"{row['execution_other_s']+row['artifact_io_s']+row['model_decision_s']:.3f}",
                   f"{row['unattributed_s']:.3f}"]
    else:
        values += ['unmeasured']*6+[f"{row['unseparated_residual_s']:.3f} (request {row['measured_request_generation_s']:.3f})"]
    lines.append('| '+' | '.join(values)+' |')
lines += ['', 'Perception components below are already included in the table above.', '',
    '| Job / state / arm | Segmentation s | Depth s | Entity measurement s | Capture / transport s |',
    '| --- | ---: | ---: | ---: | ---: |']
for row in rows:
    components = row.get('perception_components_s')
    values = [f"{row['job']} / {row['case']} / {row['arm']}"]
    if components is not None:
        assert abs(sum(components.values())-row['perception_s']) < 1e-6
        values += [f'{value:.3f}' for value in components.values()]
    else:
        values += ['unmeasured']*4
    lines.append('| '+' | '.join(values)+' |')
args.output.with_suffix('.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(dict(complete_episodes=len(rows), instrumented=sum(r['instrumented'] for r in rows),
    output=str(args.output))))
