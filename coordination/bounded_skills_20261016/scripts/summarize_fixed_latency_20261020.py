"""Summarize N1 fixed-state pairs; keep whole episodes and VLA pilots separate."""
import argparse
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path


def distribution(values):
    values = sorted(values)
    if not values:
        return {'n': 0, 'median': None, 'p90': None}
    at = .9*(len(values)-1)
    lo = int(at)
    hi = min(lo+1, len(values)-1)
    return {'n': len(values), 'median': statistics.median(values),
        'p90': values[lo]+(values[hi]-values[lo])*(at-lo)}


def read_lines(path):
    return [json.loads(line) for line in path.open() if line.strip()] if path.exists() else []


def reference(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def collect(directory, registration):
    records, missing = [], []
    for index, row in enumerate(registration['cases']):
        case_dir = directory/f'case{index:03d}'
        summary_path = case_dir/'summary.json'
        if not summary_path.exists():
            missing.append(index)
            continue
        summary = json.loads(summary_path.read_bytes())
        if summary['status'] != 'physical_result':
            raise ValueError(f'not a closed physical result: {summary_path}')
        loops = read_lines(case_dir/'loops.jsonl')
        sam = read_lines(case_dir/'sam_calls.jsonl')
        record = {'index': index, 'case': row['case']['name'], 'domain': row['domain'],
            'runner': row['runner'], 'category': row['case'].get('category'),
            'source': reference(summary_path), 'sam_calls': len(sam),
            'sam_rpc_s': sum(event['wall_s'] for event in sam),
            'sam_methods': dict(Counter(event['method'] for event in sam)),
            'sam_prompt_distribution': dict(Counter(event.get('prompt') or '<none>' for event in sam))}
        if row['runner'] == 'bounded_episode':
            record.update(success=summary['success'], wall_s=summary['wall_s'],
                sim_steps=summary['sim_steps'], decisions=summary['decisions'],
                initial_physics_sha256=summary.get('initial_physics_sha256'),
                choice_chunks=summary['candidate_ids'],
                selected_ids=[cid for chunk in summary['candidate_ids'] if chunk for cid in chunk],
                loop_s=[loop['loop_s'] for loop in loops],
                request_s=[loop['request_s'] for loop in loops],
                decision_s=[loop['decision_s'] for loop in loops],
                execution_s=[loop['execution_s'] for loop in loops],
                candidate_counts=[len(loop['request']['candidates']) for loop in loops],
                request_json_bytes=[len(json.dumps(loop['request'],separators=(',',':'),
                    ensure_ascii=False).encode()) for loop in loops],
                timing_categories=[loop['timings']['main_thread_exclusive_s'] for loop in loops])
        else:
            trials = summary['trials']
            if len(trials) != 1:
                raise ValueError('a fixed latency VLA pilot must contain exactly one trial')
            trial = trials[0]
            choices = read_lines(Path(trial['choices']['path']))
            executions = [detail['execution'] for choice in choices
                for detail in choice.get('execution_details', [])
                if 'stop_reason' in detail.get('execution', {}) and 'preparation' in detail['execution']]
            if len(executions) != 1:
                raise ValueError('expected one fallback in the registered pilot')
            execution = executions[0]
            record.update(success=trial['success'], branch_wall_s=trial['wall_s'],
                sim_steps=trial['sim_steps'], reason=trial['reason'], trial_seed=trial['trial_seed'],
                initial_physics_sha256=trial['initial_physics_sha256'],
                controls=len(execution['trace']), public_checks=len(execution['checks']),
                fallback_timing_s=execution['timing_s'],
                first_continuation_status=(summary.get('continuation') or {}).get('status'),
                vla_inputs=trial.get('vla_inputs'), vla_predictions=trial.get('vla_predictions'),
                scope='one VLA subtask and first self continuation; not whole episode')
        records.append(record)
    episodes = [record for record in records if record['runner'] == 'bounded_episode']
    aggregated = {field: distribution([value for record in episodes for value in record[field]])
        for field in ('loop_s','request_s','decision_s','execution_s','candidate_counts','request_json_bytes')}
    aggregated['whole_episode_wall_s'] = distribution([record['wall_s'] for record in episodes])
    aggregated['sam_calls_per_whole_episode'] = distribution([record['sam_calls'] for record in episodes])
    aggregated['whole_episode_success'] = {'success': sum(record['success'] for record in episodes),
        'n': len(episodes)}
    return {'records': records, 'missing_indices': missing, 'whole_episode_aggregates': aggregated}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    registration = json.loads(args.manifest.read_bytes())
    if len(registration['cases']) != 32 or registration['training'] or registration['confirmation']:
        raise ValueError('expected the registered fixed32 development cohort')
    arms = {arm: collect(args.root/arm, registration) for arm in ('baseline','optimized')}
    paired = []
    left = {row['index']: row for row in arms['baseline']['records']}
    right = {row['index']: row for row in arms['optimized']['records']}
    for index in sorted(left.keys() & right.keys()):
        a,b=left[index],right[index]
        pair = {'index':index,'case':a['case'],'runner':a['runner'],
            'baseline_success':a['success'],'optimized_success':b['success'],
            'outcome_equal':a['success']==b['success'],
            'initial_physics_hash_equal': (a['initial_physics_sha256']==b['initial_physics_sha256']
                if a['initial_physics_sha256'] and b['initial_physics_sha256'] else None)}
        if a['runner']=='bounded_episode':
            pair.update(whole_episode_wall_s=[a['wall_s'],b['wall_s']],
                choice_chunks_equal=a['choice_chunks']==b['choice_chunks'],
                selected_ids_equal=a['selected_ids']==b['selected_ids'],
                decisions=[a['decisions'],b['decisions']],sim_steps=[a['sim_steps'],b['sim_steps']])
        else:
            pair.update(branch_wall_s=[a['branch_wall_s'],b['branch_wall_s']],
                trial_seed_equal=a['trial_seed']==b['trial_seed'],
                controls=[a['controls'],b['controls']],public_checks=[a['public_checks'],b['public_checks']])
        paired.append(pair)
    report={'scope':'N1 only; 30 whole episodes and 2 separately reported VLA continuation pilots',
        'manifest':reference(args.manifest),'script':reference(Path(__file__)),
        'complete':all(not arm['missing_indices'] for arm in arms.values()),
        'arms':arms,'paired':paired,'paired_n':len(paired),'training':False,
        'limits':['Source scopes differ intentionally; request-byte equality is not expected.',
            'Missing results stay missing, not failures or successes.',
            'JSON bytes are measured; model prompt token counts are not estimated.',
            'No N8 throughput or model choice-accuracy claim.']}
    with args.output.open('x') as stream:
        json.dump(report,stream,indent=2)
        stream.write('\n')
    print(json.dumps({'complete':report['complete'],'paired_n':len(paired),
        'arms':{key:value['whole_episode_aggregates'] for key,value in arms.items()}}))


if __name__=='__main__':
    main()
