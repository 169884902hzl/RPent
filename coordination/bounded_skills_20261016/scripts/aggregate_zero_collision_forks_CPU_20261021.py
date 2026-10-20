"""Close registered same-state collision forks, retaining all unknown outcomes."""
import argparse
import ast
from collections import Counter,defaultdict
import hashlib
import json
import math
from pathlib import Path


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def wilson(k,n):
    if not n:return None
    z=1.959963984540054;p=k/n;scale=1+z*z/n
    centre=(p+z*z/(2*n))/scale
    radius=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/scale
    return {'k':k,'n':n,'rate':p,'wilson95':[centre-radius,centre+radius]}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--parent-manifest',type=Path)
    p.add_argument('--results',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();plan=json.loads(a.manifest.read_bytes())
    parent=json.loads(a.parent_manifest.read_bytes()) if a.parent_manifest else plan
    if plan['jobs']!=parent['jobs']:raise ValueError('repair changed the registered cohort')
    methods=set()
    for ref in (plan['script'],parent['script']):
        path=Path(ref['path'])
        if digest(path)!=ref['sha256']:raise ValueError('registered script changed')
        function=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='changed_contacts')
        methods.add(ast.dump(function,include_attributes=False))
    if len(methods)!=1:raise ValueError('contact criteria changed across program-error repair')
    rows=[];counts=Counter();by_skill=defaultdict(Counter);by_domain=defaultdict(Counter)
    for i,registered in enumerate(plan['jobs']):
        paths=[a.results/f'case{i:03d}/summary.json',*sorted(a.results.glob(f'case{i:03d}_attempt*/summary.json'))]
        closed=[p for p in paths if p.exists()]
        if len(closed)!=1:raise ValueError('position must close once: '+str(i))
        path=closed[0];r=json.loads(path.read_bytes())
        if r['registered_action']!=registered or r['source_commit']!=plan['source_commit']:
            raise ValueError('row binding differs')
        on,off=r['arms']
        if {arm['initial_physics_sha256'] for arm in r['arms']}!={r['common_state']['physics_sha256']}:
            raise ValueError('full common initial SHA mismatch')
        if not r['new_common_complete_integration_available']:raise ValueError('incomplete new branch start')
        if len({arm['public_screen_input_sha256'] for arm in r['arms']})!=1:
            raise ValueError('paired public screen inputs differ')
        reconstruction=r.get('public_frame_restoration',{})
        if reconstruction.get('source')!='fresh_dual_view_after_legacy_physics_restore':
            raise ValueError('current error rates require coherent freshly captured public frames')
        private_truth=('clear' if off['safe_route_completion'] is True else
            'collision' if off['physical_collision'] is True else 'unknown')
        screen=on.get('screen') or {}
        prediction=('reject_collision' if screen.get('collision') is True else
            'admit' if screen.get('passed') is True else 'other_rejection')
        result=({'reject_collision/clear':'FP','reject_collision/collision':'TP',
            'admit/clear':'TN','admit/collision':'FN'}.get(prediction+'/'+private_truth,'unknown'))
        for c in (counts,by_skill[registered['candidate']['skill']],by_domain[registered['domain']]):
            c['positions']+=1;c[result]+=1;c['off_physical']+=off['steps_used']>0
        rows.append({'index':i,'case':registered['case']['name'],'skill':registered['candidate']['skill'],
            'domain':registered['domain'],'prediction':prediction,'off_private_truth':private_truth,'classification':result,
            'on_steps':on['steps_used'],'off_steps':off['steps_used'],'on_stop':on['stop_reason'],
            'off_stop':off['stop_reason'],'off_safe_route_completion':off['safe_route_completion'],
            'off_payload':off['payload'],'off_new_contact_count':off['new_contact_count'],
            'historical_complete_integration_available':r['historical_complete_integration_available'],
            'common_initial_physics_sha256':r['common_state']['physics_sha256'],
            'diagnostic_script':r.get('diagnostic_script',parent['script']),
            'public_frame_restoration':reconstruction,
            'summary':{'path':str(path),'sha256':digest(path)},
            'private_contact_trace':{'path':off['private_contact_trace'],'sha256':digest(Path(off['private_contact_trace']))}})
    a.output.mkdir(exist_ok=False,parents=True)
    records=a.output/'rows.jsonl';records.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    fp,tp,tn,fn=(counts[k] for k in ('FP','TP','TN','FN'))
    report={'source_commit':plan['source_commit'],'counts':dict(counts),
        'by_skill':{k:dict(v) for k,v in by_skill.items()},'by_domain':{k:dict(v) for k,v in by_domain.items()},
        'clear_route_rejection_rate':wilson(fp,fp+tn),
        'false_fraction_among_classified_collision_rejections':wilson(fp,fp+tp),
        'missed_collision_rate_within_old_rejected_cohort':wilson(fn,fn+tp),
        'agreement':wilson(tp+tn,tp+tn+fp+fn),'full_initial_sha_mismatches':0,
        'unknown_positions':[r['index'] for r in rows if r['classification']=='unknown'],
        'rows':{'path':str(records),'sha256':digest(records)},'manifest':{'path':str(a.manifest),'sha256':digest(a.manifest)},
        'parent_manifest':({'path':str(a.parent_manifest),'sha256':digest(a.parent_manifest)} if a.parent_manifest else None),
        'scope':'54 distinct historical captured state/action pairs from the old-rejected census. Shared new complete starts; historical integration omissions retained. Conditional cohort only; no population false-negative rate or whole-task success claim.',
        'private_truth_scope':'OFF reached endpoint and retained payload without new/deeper robot/payload scene contact => clear; new/deeper contact => collision; other outcomes remain unknown. Raw private traces retained.',
        'training':False,'confirmation':False,'physics_replayed_by_this_aggregator':0}
    (a.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)


if __name__=='__main__':main()
