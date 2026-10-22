"""Continue two recorded original policy endpoints with measured bounded skills."""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pickle
import subprocess
import sys
from types import SimpleNamespace


def write(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2,default=str)


def checked(ref):
    p=Path(ref['path'])
    assert hashlib.sha256(p.read_bytes()).hexdigest()==ref['sha256'],str(p)
    return p


def hooks(source):
    p=source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py'
    spec=importlib.util.spec_from_file_location('handoff_hooks',p)
    h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
    return h


def worker(a,plan):
    os.environ['LIBERO_TYPE']='standard'
    h=hooks(a.source)
    # The original diagnostic imports robosuite before original_session().
    # Bootstrap the facade first, as the shared hybrid-repair launcher does.
    h.bootstrap_source('original',evaluation='hybrid_repair')
    h.install_d2_restore_compatibility()
    from scripts import probe_bounded_hybrid_d2 as probe
    from scripts import probe_bounded_hybrid_repair as repair
    from rpent.utils.rpc.http_rpc import HttpRpcClient

    row=plan['rows'][a.worker]
    assignment=json.loads((a.output/'assignment.json').read_bytes())
    endpoints={k:HttpRpcClient(assignment[k+'_url']) for k in ('sam3','vla')}
    with probe.runtime(row['case'],endpoints,a.output/'episode',domain='original') as (facade,adapter,policy,timings):
        defaults={name:copy.deepcopy(getattr(adapter,name)) for name in repair.SCHEMA6_REPLAY_FIELDS}
        saved=pickle.loads(checked(row['endpoint']).read_bytes())
        probe.restore_checkpoint(facade,adapter,policy,saved)
        expected=probe.snapshot_digest(saved['physics'])
        assert probe.snapshot_digest(facade.snapshot())==expected
        adapter.allow_vla=False
        old_request=copy.deepcopy(adapter.latest_request)
        if old_request['schema_version']!=plan['schema_version']:
            repair.rebuild_schema6_replay(adapter,old_request,defaults)
        else:
            adapter.refresh();adapter.request(k=4)
        before=facade.goal_status()
        assert before['satisfied'][row['registered_goal_index']] and not before['done']
        specs,unsupported=probe.split_subtasks(before['goals'],adapter.ex.instruction)
        assert not unsupported
        next_spec=next(s for s in specs if not before['satisfied'][s['goal_index']])
        assert next_spec['goal_index']!=row['registered_goal_index']
        directory=a.output/'continuation';directory.mkdir()
        result=repair.first_self_chunk(facade,adapter,policy,next_spec,directory)
        after=facade.goal_status()
        write(a.output/'summary.json',{'case':row['case'],'source_commit':plan['source_commit'],
            'original_failed_policy_endpoint':row['endpoint'],'policy_seed':row['policy_seed'],
            'exact_complete_endpoint_sha256':expected,'registered_goal_index':row['registered_goal_index'],
            'before':before,'next_subtask':next_spec,'continuation':result,'after':after,
            'actual_new_controls':sum(r['steps_used'] for r in result.get('receipts',[])),
            'policy_replayed':False,'policy_called_for_continuation':False,
            'training':False,'D2':False,'PRO':False,'confirmation':False,
            'scope':'functional continuation from recorded original policy endpoint; no new episode success estimate'})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--worker',type=int)
    p.add_argument('--preflight',action='store_true')
    a=p.parse_args();a.source=a.source.resolve(strict=True);sys.path.insert(0,str(a.source))
    plan=json.loads(a.manifest.read_bytes())
    assert not plan['training'] and len(plan['rows'])==2
    for row in plan['rows']:
        assert row['case']['episode']['suite'] in {'libero_spatial','libero_object','libero_goal','libero_10'}
        checked(row['endpoint']);checked(row['case']['bddl'])
    if a.preflight:print('two original captured endpoints validated; no controls');return 0
    if a.worker is not None:return worker(a,plan)
    os.environ['PYTHONPATH']=str(a.source);os.chdir(a.source)
    h=hooks(a.source);h.bootstrap_source('original',evaluation='hybrid_repair')
    from scripts.probe_bounded_feasibility import services
    a.output.mkdir(parents=True,exist_ok=True)
    service=SimpleNamespace(source=a.source,output=a.output,sam3_entry=checked(plan['sam_entry']))
    with h.owned_services(service,services,vla=True) as endpoints:
        for i,row in enumerate(plan['rows']):
            out=a.output/f'case{i:03d}';out.mkdir()
            write(out/'assignment.json',{k+'_url':v._base_url for k,v in endpoints.items()})
            cmd=[sys.executable,str(Path(__file__).resolve()),'--source',str(a.source),
                '--manifest',str(a.manifest),'--output',str(out),'--worker',str(i)]
            with (out/'worker.log').open('x') as log:
                subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
            print(json.dumps({'closed':str(out/'summary.json')}),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
