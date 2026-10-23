"""Report paired permissive preparation and public contact skill measurements."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics


def reference(path):
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def checked(ref):
    path=Path(ref['path']);assert reference(path)==ref,path;return path


def endpoint_error(detail):
    if detail.get('endpoint_error_m') is not None:return detail['endpoint_error_m']
    checks=detail.get('component',{}).get('receipt',{}).get('expectation_checks',[])
    return next((row['measured'] for row in checks if row['condition']['metric']=='endpoint_error_m'),None)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--panel',choices=['N2','skills'],required=True);parser.add_argument('--suffix',default='_r1')
    parser.add_argument('--compare',type=Path,help='Previously closed trials.jsonl for the same panel')
    args=parser.parse_args();plan=json.loads((args.run/'preparation'/(args.panel+args.suffix+'.json')).read_bytes())
    rows=[];sources=[]
    for i,job in enumerate(plan['jobs']):
        ref=json.loads((args.run/(args.panel+args.suffix)/f'closed_{i:03d}.json').read_bytes())
        raw=json.loads(checked(ref).read_bytes());sources.append(ref)
        for trial in raw['trials']:
            result=dict(trial,case=raw['case']['name'],category=raw['case']['category'])
            if trial['status']=='physical_result':
                full=json.loads(checked(trial['record']).read_bytes());detail=full['preparation_or_skill'];metrics=trial['metrics']
                result.update(endpoint_error_m=endpoint_error(detail),
                    arrived=detail.get('arrived',endpoint_error(detail) is not None and endpoint_error(detail)<=.012),
                    controls=metrics['samples'],
                    new_contact_gt_1um=bool(metrics['new_or_deeper_contacts_gt_1um']),
                    new_contact_gt_1mm=bool(metrics['new_or_deeper_contacts_gt_1mm']),
                    max_non_target_displacement_m=metrics['max_non_target_displacement_m'],
                    policy_invoked=full['policy_result'] is not None,
                    adaptive_motion_executed=bool(detail.get('steps_used',0)) if args.panel=='skills' else False,
                    adaptive_motion_steps=detail.get('steps_used',0) if args.panel=='skills' else 0,
                    measured_advance_m=detail.get('advance_m'),
                    motion_stop_reason=detail.get('stop_reason',detail.get('reason',detail.get('component',{}).get('reason'))))
            rows.append(result)
    expected=len(plan['jobs'])*3*(2 if args.panel=='N2' else 1)
    assert len(rows)==expected,(len(rows),expected)
    if args.panel=='N2':
        grouped=defaultdict(list)
        for row in rows:grouped[(row['case'],row['repeat'])].append(row)
        for key,pair in grouped.items():
            assert len(pair)==2,key
            sha={r['complete_initial_sha256'] for r in pair if r['status']=='physical_result'}
            assert len(sha)<=1,key
    args.output.mkdir(parents=True,exist_ok=False)
    data=args.output/'trials.jsonl';data.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
    groups={}
    for category,arm in sorted({(r['category'],r['arm']) for r in rows}):
        all_rows=[r for r in rows if (r['category'],r['arm'])==(category,arm)]
        measured=[r for r in all_rows if r['status']=='physical_result']
        executed=[r for r in measured if r['controls']>0]
        errors=[r['endpoint_error_m'] for r in measured if r['endpoint_error_m'] is not None]
        groups[category+'|'+arm]={'trials':len(all_rows),'measured':len(measured),
            'unknown':len(all_rows)-len(measured),'successes':sum(r['success'] for r in measured),
            'prep_or_setup_controls_nonzero':len(executed),'new_contact_gt_1um':sum(r['new_contact_gt_1um'] for r in executed),
            'new_contact_gt_1mm':sum(r['new_contact_gt_1mm'] for r in executed),
            'contact_rate_denominator_executed_only':len(executed),
            'max_non_target_displacement_m':max((r['max_non_target_displacement_m'] for r in measured),default=None),
            'median_endpoint_error_m':statistics.median(errors) if errors else None,
            'arrived':sum(r['arrived'] for r in measured),
            'max_endpoint_error_m':max(errors) if errors else None,
            'endpoint_errors_measured':len(errors),'policy_invoked':sum(r['policy_invoked'] for r in measured),
            'adaptive_motion_executed':sum(r['adaptive_motion_executed'] for r in measured),
            'stop_reasons':dict(Counter(r.get('motion_stop_reason',r.get('reason')) for r in all_rows))}
    manifest={'panel':args.panel,'states':len(plan['jobs']),'trials':len(rows),'groups':groups,
        'data':reference(data),'raw_summaries':sources,'private_metrology_not_controller_input':True,
        'setup_selector_uses_private_goal_predicates':True,'controller_uses_private_fixture_joint_angles':False,
        'training_executed':False,'PRO':False,'D2':False,'confirmation':False}
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    lines=['# '+args.panel+' 接触与结果', '',
        '| 类别/方法 | 成功/实测 | unknown | 实际运动 | 新/更深接触 >1µm | >1mm | 非目标最大位移 m | 终点误差中位 m | 自适应推进已执行 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for key,r in groups.items():
        lines.append(f"| {key} | {r['successes']}/{r['measured']} | {r['unknown']} | {r['prep_or_setup_controls_nonzero']} | {r['new_contact_gt_1um']}/{r['contact_rate_denominator_executed_only']} | {r['new_contact_gt_1mm']}/{r['contact_rate_denominator_executed_only']} | {r['max_non_target_displacement_m']} | {r['median_endpoint_error_m']} | {r['adaptive_motion_executed']} |")
    lines+=['','每状态重复3次；不把重复次数视为独立布局数。unknown与零步拒绝单列，不把未执行动作当作安全成功。',
        '接触是相对本分支起点新增或加深的手部–场景穿入；1µm与1mm分别统计。非目标物体位移用私有body origin度量，仅用于结果分析。',
        'N2成功是准备后π调用结束时原登记子目标谓词；到点误差单列，准备段放行不等于到点。',
        '技能结果含公开接近/闭合的准备阶段；自适应推进真正运行次数单列，准备失败不冒充推进试验。',
        '诊断的规则 oracle 用私有任务谓词选择公开准备选项；执行控制器的动作与进展测量只用公开 RGB-D、本体状态及静态机器人几何。原始 private_truth_used_for_control 字段仅描述这个控制器。']
    (args.output/'RESULTS.md').write_text('\n'.join(lines)+'\n')
    if args.panel=='N2':
        table=['| 状态 | screened 成功/3 | permissive 成功/3 | 调π screened/permissive | 宽容到点/3 | >1µm / >1mm | 终点误差中位 m |',
            '|---|---:|---:|---:|---:|---:|---:|']
        for case in dict.fromkeys(r['case'] for r in rows):
            a=[r for r in rows if r['case']==case and r['arm']=='screened' and r['status']=='physical_result']
            b=[r for r in rows if r['case']==case and r['arm']=='permissive' and r['status']=='physical_result']
            errors=[r['endpoint_error_m'] for r in b if r['endpoint_error_m'] is not None]
            table.append(f"| {case} | {sum(r['success'] for r in a)}/{len(a)} | {sum(r['success'] for r in b)}/{len(b)} | {sum(r['policy_invoked'] for r in a)}/{sum(r['policy_invoked'] for r in b)} | {sum(r['arrived'] for r in b)}/{len(b)} | {sum(r['new_contact_gt_1um'] for r in b)} / {sum(r['new_contact_gt_1mm'] for r in b)} | {statistics.median(errors) if errors else None} |")
        (args.output/'paired_table.md').write_text('\n'.join(table)+'\n')
    if args.compare:
        prior={(r['case'],r['arm'],r['repeat']):r
            for r in map(json.loads,args.compare.read_text().splitlines())}
        pairs=[]
        for row in rows:
            old=prior[(row['case'],row['arm'],row['repeat'])]
            known=old['status']==row['status']=='physical_result'
            if known:
                assert old['complete_initial_sha256']==row['complete_initial_sha256'],row['case']
            pairs.append({'case':row['case'],'arm':row['arm'],'repeat':row['repeat'],
                'complete_initial_sha_matched':True if known else None,'before':old,'after':row})
        data=args.output/'paired_with_previous.jsonl'
        data.write_text(''.join(json.dumps(p,sort_keys=True)+'\n' for p in pairs))
        table=['| 状态 | 修前成功 | 修后成功 | 真正推进 修前/修后 | 修后累计推进中位 m |',
            '|---|---:|---:|---:|---:|']
        for case in dict.fromkeys(p['case'] for p in pairs):
            selected=[p for p in pairs if p['case']==case]
            before=[p['before'] for p in selected if p['before']['status']=='physical_result']
            after=[p['after'] for p in selected if p['after']['status']=='physical_result']
            advances=[p['measured_advance_m'] for p in after if p['measured_advance_m'] is not None]
            table.append(f"| {case} | {sum(p['success'] for p in before)}/{len(before)} | {sum(p['success'] for p in after)}/{len(after)} | {sum(p['adaptive_motion_executed'] for p in before)}/{sum(p['adaptive_motion_executed'] for p in after)} | {statistics.median(advances) if advances else None} |")
        (args.output/'paired_with_previous.md').write_text('\n'.join(table)+'\n')
        manifest.update(paired_with_previous=reference(data),previous_trials=reference(args.compare),
            complete_initial_sha_matched_pairs=sum(p['complete_initial_sha_matched'] is True for p in pairs),
            improved=sum(p['after'].get('success',False) and not p['before'].get('success',False)
                for p in pairs if p['complete_initial_sha_matched']),
            regressed=sum(p['before'].get('success',False) and not p['after'].get('success',False)
                for p in pairs if p['complete_initial_sha_matched']))
        (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest))


if __name__=='__main__':main()
