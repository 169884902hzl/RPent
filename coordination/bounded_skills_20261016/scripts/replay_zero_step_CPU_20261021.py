"""Rejudge retained public route inputs and join exact receipt census keys."""
import argparse
import gzip
import hashlib
import json
import pickle
import sys
import time
import importlib.util
from collections import Counter
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--calls',type=Path,required=True)
    p.add_argument('--census',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--before-source',type=Path)
    a=p.parse_args();sys.path.insert(0,str(a.source))
    from robots.libero.bounded_screen import PublicRouteScreen
    legacy=None
    if a.before_source:
        spec=importlib.util.spec_from_file_location('saved_baseline_route',a.before_source/'robots/libero/bounded_screen.py')
        legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
    census={}
    for line in a.census.read_text().splitlines():
        row=json.loads(line)
        key=(row['file'],row.get('row_index'),row['candidate_id'])
        census.setdefault(key,[]).append(row)
    a.output.mkdir(parents=True,exist_ok=False)
    counts=Counter();errors=[]
    with (a.output/'rows.jsonl').open('x',buffering=1) as out:
        for line in a.calls.read_text().splitlines():
            row=json.loads(line)
            if row['kind']!='route':continue
            try:
                raw=gzip.decompress(Path(row['input']).read_bytes())
                if hashlib.sha256(raw).hexdigest()!=row['input_sha256']:raise ValueError('input changed')
                old,args,kwargs=pickle.loads(raw)
                poses=args[0]
                before=row['result']
                if legacy is not None:
                    old_copy,_,_=pickle.loads(raw)
                    baseline=legacy.PublicRouteScreen(old_copy.points,old_copy.geometry,old_copy.ik,opening=old_copy.opening,
                        contact_points=old_copy.target,contact_allowed=old_copy.contact_allowed,
                        payload_local=old_copy.payload,initial_pose=poses[0],
                        measured_scene_points=old_copy.measured_scene_points,
                        measured_target_points=old_copy.measured_target_points)
                    baseline.contact_axis=getattr(old_copy,'contact_axis',None)
                    baseline.contact_origin=getattr(old_copy,'contact_origin',None)
                    before=baseline(*args,**kwargs)
                rebuilt=PublicRouteScreen(old.points,old.geometry,old.ik,opening=old.opening,
                    contact_points=old.target,contact_allowed=old.contact_allowed,
                    payload_local=old.payload,initial_pose=poses[0],
                    measured_scene_points=old.measured_scene_points,
                    measured_target_points=old.measured_target_points)
                rebuilt.contact_axis=old.contact_axis;rebuilt.contact_origin=old.contact_origin
                t=time.perf_counter();result=rebuilt(*args,**kwargs);elapsed=time.perf_counter()-t
                ctx=row['context'];key=(ctx.get('source_choices'),ctx.get('decision_index'),ctx.get('candidate_id'))
                matched=census.get(key,[])
                counts['routes']+=1
                counts['recorded_reject']+=not row['result']['passed']
                counts['recorded_vs_cold_before_differences']+=row['result']['passed']!=before['passed']
                counts['before_reject']+=not before['passed'];counts['after_reject']+=not result['passed']
                counts['released']+=not before['passed'] and result['passed']
                counts['new_reject']+=before['passed'] and not result['passed']
                counts['exact_census_key_matches']+=bool(matched)
                out.write(json.dumps(dict(input=row['input'],input_sha256=row['input_sha256'],
                    context=ctx,recorded=row['result'],before=before,after=result,wall_s=elapsed,
                    census=[{'file':e['file'],'line':e['line'],'reason':e['primary_reason']} for e in matched]))+'\n')
            except Exception as exc:
                errors.append({'input':row['input'],'error':repr(exc)})
    result=dict(counts=counts,errors=errors,source=str(a.source),before_source=str(a.before_source),physics_steps=0,rpc_calls=0,
        scope='same captured geometry/routes; isolates current-overlap rule; does not reconstruct absent raw pixels or certify private collision truth',
        calls={'path':str(a.calls),'sha256':hashlib.sha256(a.calls.read_bytes()).hexdigest()},
        census={'path':str(a.census),'sha256':hashlib.sha256(a.census.read_bytes()).hexdigest()})
    (a.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
    if errors:raise RuntimeError('CPU rejudge errors retained')


if __name__=='__main__':main()
