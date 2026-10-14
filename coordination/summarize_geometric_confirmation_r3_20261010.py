"""Score the independent, predeclared grasp confirmations without replacing trials."""
import argparse
from collections import Counter
import datetime
import hashlib
import json
from pathlib import Path
import statistics

from coordination.summarize_registered_grasp_v3r9 import confusion, metric
from coordination.classify_grasp_contact_phases_20261010 import diagnose

LOCKED_V3 = 'd8ea8a435e20e00326d34be3e0be53a1ab7983fe411e114cd11e5234dfcdf81f'


def pin(path):
    return {'path': str(path.resolve()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--parent', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    producer = args.output / Path(__file__).name
    producer.write_bytes(Path(__file__).read_bytes())
    rows, groups, inputs, plans, seen_states, classes = [], {}, [], [], set(), set()
    for parent in args.parent:
        submission_path = parent / 'preparation/formal_submission.json'
        submitted = json.loads(submission_path.read_text())
        plan_path = Path(submitted['plan']['path'])
        if pin(plan_path)['sha256'] != submitted['plan']['sha256']:
            raise ValueError('registered confirmation plan changed')
        plan = json.loads(plan_path.read_text())
        if (plan['cohort'] != 'confirmation' or not plan['confirmation'] or plan['training_allowed']
                or plan['PRO_files_read'] or plan['confirmation_states_selected_using_policy_outcomes']):
            raise ValueError('expected independent, permanently isolated confirmation')
        source = Path(plan['source_path'])
        for r in plan['source_snapshot']['files']:
            if pin(source / r['relative_path'])['sha256'] != r['sha256']:
                raise ValueError('confirmation source changed')
        if pin(source / 'robots/libero/v5_grasp_truth.py')['sha256'] != LOCKED_V3:
            raise ValueError('confirmation must use locked v3')
        cases = {c['name']: c for c in plan['cases']}
        kinds={c['type'] for c in cases.values()}
        if len(kinds)!=1 or kinds & classes:
            raise ValueError('expected one distinct object class per confirmation plan')
        classes.update(kinds)
        if len(cases) < 100 or any(not c['permanent_training_exclusion'] for c in cases.values()):
            raise ValueError('at least100 permanently excluded registered states required')
        for c in cases.values():
            if c['state_sha256'] in seen_states:
                raise ValueError('confirmation state repeated across methods/classes')
            seen_states.add(c['state_sha256'])
        plans.append({'plan':pin(plan_path),'submission':pin(submission_path),
            'source_identity':pin(source/'source_identity_v3r9.json'),
            'selection_evidence':plan['selection_evidence'],'confirmation_pool':plan['confirmation_pool']})
        selected, seen, infra, fault_cases, fault_attempts = [], set(), [], set(), []
        jobroots = [parent / ('job' + submitted[key].split(';')[0])
                    for key in ('startup_job', 'formal_job')]
        supplement = parent / 'preparation/infrastructure_resume.json'
        if supplement.exists():
            resume = json.loads(supplement.read_text())
            resume_root = Path(resume['resume_root'])
            supplement_submission = resume_root / 'preparation/formal_submission.json'
            resume_submitted = json.loads(supplement_submission.read_text())
            resume_plan_path = Path(resume_submitted['plan']['path'])
            if pin(resume_plan_path)['sha256'] != resume_submitted['plan']['sha256']:
                raise ValueError('startup supplement plan changed')
            resumed_plan = json.loads(resume_plan_path.read_text())
            if (resumed_plan['source_path'] != plan['source_path']
                    or resumed_plan['conditions'] != plan['conditions']
                    or resumed_plan['original_confirmation_plan'] != pin(plan_path)):
                raise ValueError('startup supplement changed confirmation method')
            for fault in resumed_plan['startup_faults']:
                path = Path(fault['input'])
                if pin(path)['sha256'] != fault['input_sha256']:
                    raise ValueError('original startup fault ledger changed')
                raw = json.loads(path.read_text().splitlines()[fault['line'] - 1])
                if (not raw.get('infrastructure_failure') or raw.get('first_attempt')
                        or raw.get('error_stage') != 'startup'):
                    raise ValueError('a physical result was retried')
            if any(case != cases[case['name']] for case in resumed_plan['cases']):
                raise ValueError('supplement changed a registered confirmation state')
            plans[-1]['startup_only_supplement'] = {
                'registration': pin(supplement), 'plan': pin(resume_plan_path),
                'submission': pin(supplement_submission)}
            jobroots.extend(resume_root / ('job' + resume_submitted[key].split(';')[0])
                            for key in ('startup_job', 'formal_job'))
        for jobroot in jobroots:
            for p in sorted(jobroot.glob('part*/probe/infrastructure_attempts.jsonl')):
                data = p.read_bytes()
                if data and not data.endswith(b'\n'):
                    raise ValueError('infrastructure ledger is still being written')
                ref = pin(p)
                inputs.append(ref)
                for line_no, line in enumerate(data.splitlines(), 1):
                    raw = json.loads(line)
                    if raw['case'] != cases[raw['case']['name']]:
                        raise ValueError('infrastructure attempt changed registered state')
                    if raw.get('infrastructure_failure'):
                        fault_cases.add(raw['case']['name'])
                        first = raw.get('first_attempt') or {}
                        fault_attempts.append({
                            'case': raw['case']['name'], 'input': ref, 'line': line_no,
                            'attempt_index': raw.get('attempt_index'),
                            'error_stage': raw.get('error_stage'),
                            'raised_error': raw.get('raised_error'),
                            'physical_controls': max(first.get('executed_actions', 0),
                                (first.get('receipt') or {}).get('sim_steps_used', 0)),
                            'instrument_fault_after_execution': bool(raw.get('instrument_fault_after_execution'))})
            for p in sorted(jobroot.glob('part*/probe/episodes.jsonl')):
                data=p.read_bytes()
                if data and not data.endswith(b'\n'):
                    raise ValueError('physical ledger is still being written')
                ref=pin(p);inputs.append(ref)
                for line_no,l in enumerate(data.splitlines(),1):
                    raw=json.loads(l);case=raw['case'];name=case['name']
                    if case != cases[name]:raise ValueError('physical case differs from registered plan')
                    if raw.get('case_had_infrastructure_failure') or raw.get('infrastructure_failure'):
                        fault_cases.add(name)
                    if raw.get('infrastructure_failure'):
                        infra.append({'case':name,'input':ref,'line':line_no});continue
                    if name in seen:raise ValueError('confirmation physical trial repeated')
                    seen.add(name)
                    first=raw.get('first_attempt') or {};receipt=first.get('receipt') or {}
                    truth = first.get('private_hold_truth_v3') or {}
                    diagnostic = diagnose(raw, {
                        'case': name, 'category': case['type'], 'state_sha256': case['state_sha256'],
                        'method': 'analytic_contact' if plan['conditions'][case['condition']]
                            .get('overrides', {}).get('analytic_grasp_v1') else 'pi05_contact',
                        'physical_outcome': 'success' if truth.get('success') is True else
                            'failure' if truth.get('success') is False else 'unknown'})
                    row={'group':parent.name,'case':name,'type':case['type'],
                        'layout_seed':case['layout_seed'],'state_sha256':case['state_sha256'],
                        'input':ref,'line':line_no,'registered_v3':
                            truth.get('success'),
                        'private_truth_unknown_reasons': sorted({c['unknown_reason']
                            for c in truth.get('checks', []) if c.get('unknown_reason')}),
                        'private_failed_v3_checks': diagnostic['registered_final_window_failure_samples'],
                        'private_contact_failure_class': diagnostic['contact_failure_class'],
                        'public':receipt.get('grasp_verified'),'failure_reason':
                            receipt.get('failure_reason') or raw.get('binding_error'),
                        'status':raw['status'],'physically_executed':first.get('physically_executed'),
                        'wall_s':raw.get('case_wall_s',raw.get('wall_s')),
                        'case_had_infrastructure_failure':bool(raw.get('case_had_infrastructure_failure')),
                        'physical_failures_retried':raw.get('physical_failures_retried',0),
                        'training_allowed':False}
                    if row['physical_failures_retried']:raise ValueError('confirmation failure was retried')
                    selected.append(row)
        n=len(cases);complete=seen==set(cases)
        success=metric(sum(r['registered_v3'] is True for r in selected),n)
        public=confusion(selected,'registered_v3')
        # Pending states remain in the registered agreement denominator too.
        public['agreement_all_registered']=metric(public['tp']+public['tn'],n)
        walls=[r['wall_s'] for r in selected if isinstance(r['wall_s'],(int,float))]
        groups[parent.name]={'registered_n':n,'recorded_n':len(selected),'pending_n':n-len(selected),
            'complete':complete,'success':success,'public_verifier':public,
            'failure_reasons':dict(Counter(r['failure_reason'] for r in selected)),
            'private_truth_unknown_reasons': dict(Counter(reason for r in selected
                for reason in r['private_truth_unknown_reasons'])),
            'private_failed_v3_predicate_case_counts': dict(Counter(reason for r in selected
                if r['registered_v3'] is False for reason in r['private_failed_v3_checks'])),
            'private_contact_failure_classes': dict(Counter(r['private_contact_failure_class']
                for r in selected if r['registered_v3'] is not True)),
            'missing_cases':sorted(set(cases)-seen),'infrastructure_failures':infra,
            'infrastructure': {
                'unique_registered_cases': metric(len(fault_cases), n),
                'fault_case_names': sorted(fault_cases), 'fault_attempts': fault_attempts,
                'recovered_cases': sorted(fault_cases & seen),
                'unresolved_cases': sorted(fault_cases - seen),
                'fault_attempt_n': len(fault_attempts),
                'observed_rate_exceeds_2_percent': len(fault_cases) / n > .02,
                'denominator': 'all registered states for this object class; union across original and supplement shards'},
            'median_wall_s':statistics.median(walls) if walls else None,
            'internal_class_thresholds_passed':(success['rate']>=.90 and
                public['agreement_all_registered']['rate']>=.95) if complete else None}
        rows.extend(selected)
    output_rows=args.output/'rows.jsonl'
    output_rows.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    n=sum(g['registered_n'] for g in groups.values())
    success=metric(sum(r['registered_v3'] is True for r in rows),n)
    public=confusion(rows,'registered_v3');public['agreement_all_registered']=metric(public['tp']+public['tn'],n)
    complete=classes=={'grasp_bottle','grasp_bowl','grasp_box','grasp_cup','grasp_frypan'} and all(g['complete'] for g in groups.values())
    manifest={'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'classification':'independent_confirmation','complete_fiveclass_batch':complete,
        'plans':plans,'inputs':inputs,'records':pin(output_rows),'producer':pin(producer),
        'metric_dependency':pin(Path(metric.__code__.co_filename)),
        'private_diagnosis_dependency': pin(Path(diagnose.__code__.co_filename)),
        'groups':groups,'overall_success':success,'overall_public_verifier':public,
        'overall_infrastructure': {
            'unique_registered_cases': metric(sum(g['infrastructure']['unique_registered_cases']['k']
                for g in groups.values()), n),
            'fault_attempt_n': sum(g['infrastructure']['fault_attempt_n'] for g in groups.values()),
            'unresolved_n': sum(len(g['infrastructure']['unresolved_cases']) for g in groups.values())},
        'internal_thresholds':{'overall':.95,'class':.90,'agreement':.95},
        'internal_thresholds_passed':(success['rate']>=.95 and
            all(g['internal_class_thresholds_passed'] for g in groups.values())) if complete else None,
        'locked_v3_sha256':LOCKED_V3,'training_allowed':False,
        'permanent_training_exclusion':True,'confirmation_physical_failures_retried':False,
        'limits':['Unknown truth, public null and pending states remain in registered denominators.',
                  'Only this independent batch determines internal thresholds; selection results do not.',
                  'Private v3 labels never enter runtime control.']}
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'complete':complete,'overall_success':success,
        'internal_thresholds_passed':manifest['internal_thresholds_passed']}))


if __name__ == '__main__':main()
