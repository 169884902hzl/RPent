"""CPU checks for episode isolation and visible launcher failures."""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_PATH = Path(__file__).resolve().parents[4]/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py'
_spec = importlib.util.spec_from_file_location('shared_gpu_launcher', _PATH)
launcher = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(launcher)


def test_timed_rpc_preserves_call_and_error(tmp_path):
    received = []
    class Client:
        _base_url = 'http://127.0.0.1:1234'
        def call(self, *args, **kwargs):
            received.append((args, kwargs))
            if args[0] == 'fail':
                raise ValueError('original error')
            return {'mask':'original'}
    path=tmp_path/'latencies.jsonl'
    with path.open('w') as log:
        rpc=launcher.TimedRPC(Client(),log)
        assert rpc.call('sam3.segment',kwargs={'point':[1,2]},timeout_s=10)=={'mask':'original'}
        with pytest.raises(ValueError,match='original error'):
            rpc.call('fail')
    assert received[0]==(('sam3.segment',),{'args':(),'kwargs':{'point':[1,2]},'timeout_s':10})
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    assert [row['error'] for row in rows]==[None,'ValueError']


def test_choice_comparison_keeps_chunk_boundaries_and_serial_difference():
    assert launcher.edit_distance([['a','b'],['c']],[['a','b'],['c']])==0
    assert launcher.edit_distance([['a','b'],['c']],[['a'],['b','c']])==2
    assert launcher.edit_distance([['a'],['b']],[['a'],['b'],['c']])==1


def test_consistency_reads_external_serial_results_and_enforces_zero_baseline(tmp_path):
    serial=tmp_path/'serial';parallel=tmp_path/'parallel'
    study={'consistency_cases':[]}
    for i in range(3):
        name=f'case{i}'
        historical=tmp_path/f'historical{i}.jsonl'
        choices=json.dumps({'decision':{'candidate_ids':['move','close','lift']}})+'\n'
        historical.write_text(choices)
        result={'success':True,'sim_steps':100+i}
        study['consistency_cases'].append({'case':{'name':name},
            'choices':{'path':str(historical),'sha256':launcher.digest(historical)},
            'historical_result':result})
        for directory in [serial/'measurements/N1'/f'{i:03d}_{name}',
                          parallel/'consistency/N8'/f'{i:03d}_{name}']:
            (directory/(name+'_oracle_k4')).mkdir(parents=True)
            (directory/'worker_summary.json').write_text(json.dumps({'result':result}))
            (directory/(name+'_oracle_k4')/'choices.jsonl').write_text(choices)
    compared=launcher.compare_three(study,parallel,8,serial)
    assert compared['all_three_within_serial_baseline']
    changed=parallel/'consistency/N8/001_case1/case1_oracle_k4/choices.jsonl'
    changed.write_text(json.dumps({'decision':{'candidate_ids':['observe']}})+'\n')
    rejected=launcher.compare_three(study,parallel,8,serial)
    assert not rejected['all_three_within_serial_baseline']
    assert rejected['cases'][1]['choice_sequence_edit_parallel']==1
    assert rejected['cases'][1]['choice_sequence_edit_baseline']==0


def test_gpu_study_finishes_without_accounting_or_waiting_for_external_n1(tmp_path,monkeypatch):
    def no_accounting(*args,**kwargs):
        raise AssertionError('compute-node accounting must not be queried')
    monkeypatch.setattr(launcher.subprocess,'check_output',no_accounting)
    def measured(args,plan,indices,endpoints,n,sampler):
        return {'n':n,'worker_errors':0,'completed_episodes_per_hour':{4:30.,8:50.,12:52.}[n]}
    monkeypatch.setattr(launcher,'run_level',measured)
    root=tmp_path/'gpu';root.mkdir()
    args=SimpleNamespace(output=root,serial_reference=tmp_path/'unfinished_serial')
    result=launcher.run_study(args,{'source_commit':'pinned'},
        {'indices':[0,1,2]}, {}, None)
    assert result['gpu_measurements_complete'] and result['offline_finalization_required']
    assert result['awaiting_external_serial'] and not result['adoption_ready']
    assert result['selected_n']==8


def test_offline_finalizer_recounts_failed_episodes_and_requires_complete_n1(tmp_path):
    path=_PATH.with_name('finalize_shared_study_20261019.py')
    spec=importlib.util.spec_from_file_location('offline_finalizer',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    serial=tmp_path/'serial';root=tmp_path/'parallel'
    serial.mkdir();root.mkdir()
    manifest=tmp_path/'manifest.json';manifest.write_text('{}')
    cases=[{'name':f'case{i}'} for i in range(3)]
    launch={'source':'/pinned/source','source_commit':'pinned','domain':'original',
        'manifest':{'path':str(manifest),'sha256':launcher.digest(manifest)},'indices':[0,1,2]}
    (serial/'launch.json').write_text(json.dumps(launch))
    (root/'launch.json').write_text(json.dumps({**launch,'serial_reference':str(serial)}))
    study={**launch,'cases':cases,'consistency_cases':[]}
    results=[{'success':i!=1,'sim_steps':10+i} for i in range(3)]
    choices=json.dumps({'decision':{'candidate_ids':['move','close','lift']}})+'\n'
    for i,case in enumerate(cases):
        historical=tmp_path/f'history{i}.jsonl';historical.write_text(choices)
        study['consistency_cases'].append({'case':case,'historical_result':results[i],
            'choices':{'path':str(historical),'sha256':launcher.digest(historical)}})
    study_path=tmp_path/'study.json';study_path.write_text(json.dumps(study))
    for directory,n,rate in [(serial/'measurements/N1',1,10.),
        (root/'measurements/N4',4,30.),(root/'measurements/N8',8,50.),
        (root/'measurements/N12',12,52.),(root/'consistency/N8',8,50.)]:
        directory.mkdir(parents=True)
        wall=3*3600/rate
        (directory/'summary.json').write_text(json.dumps({'n':n,'registered_episodes':3,
            'physical_episodes':3,'successful_episodes':2,'source_commit':'pinned',
            'startup':False,'worker_errors':0,'wall_s':wall,'completed_episodes_per_hour':3*3600/wall}))
        rows=[]
        for i,case in enumerate(cases):
            d=directory/f'{i:03d}_{case["name"]}';(d/(case['name']+'_oracle_k4')).mkdir(parents=True)
            (d/'worker_summary.json').write_text(json.dumps({'result':results[i]}))
            (d/(case['name']+'_oracle_k4')/'choices.jsonl').write_text(choices)
            rows.append({'case':case,'process_exit_code':0,'result':{**results[i],'status':'physical_result'}})
        (directory/'episodes.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
    result=module.finalize(root,study_path,launcher)
    assert result['adoption_ready'] and result['selected_n']==8
    assert result['measured_speedup']==5
    assert all(row['physical_episodes']==3 and row['successful_episodes']==2 for row in result['levels'])
    (serial/'measurements/N1/summary.json').unlink()
    with pytest.raises(FileNotFoundError):module.finalize(root,study_path,launcher)


def test_d2_worker_bootstraps_environment_before_helper_imports(tmp_path):
    source=tmp_path/'source';source.mkdir()
    for package in ['scripts','rpent','rpent/utils','rpent/utils/rpc','robots','robots/libero']:
        p=source/package;p.mkdir(parents=True,exist_ok=True);(p/'__init__.py').write_text('')
    (source/'rpent/utils/rpc/http_rpc.py').write_text('class HttpRpcClient:\n    def __init__(self,url):self._base_url=url\n')
    (source/'robots/libero/env_server.py').write_text("import sys\nassert 'mujoco' not in sys.modules, 'environment imported too late'\nBOOTSTRAPPED=True\n")
    (source/'robots/libero/v5_branch_state.py').write_text('def restore_actuators(*a): raise AssertionError()\n')
    (source/'mujoco.py').write_text('SIMULATOR_IMPORTED=True\n')
    (source/'scripts/probe_bounded_feasibility.py').write_text('import mujoco\ndef probe_config(base):return base\ndef episode(*a,**kw):raise AssertionError()\n')
    (source/'scripts/probe_bounded_hybrid_d2.py').write_text('''
from robots.libero.env_server import BOOTSTRAPPED
def evaluate_case(case,endpoints,output,plan,*,startup):
    assert BOOTSTRAPPED
    return {'status':'physical_result','actual_full_replay_success':True}
''')
    cases=[{'name':f'case{i}'} for i in range(2)]
    plan={'source_commit':'pinned','cases':cases};manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps(plan))
    output=tmp_path/'out';output.mkdir()
    args=SimpleNamespace(source=source,manifest=manifest,output=output,domain='d2',startup=False)
    result=launcher.run_level(args,plan,[0,1],{'sam3':SimpleNamespace(_base_url='http://127.0.0.1:1234')},
        2,SimpleNamespace(stage=None,summary=lambda _:{}))
    assert result['worker_errors']==0 and result['physical_episodes']==2
    assert result['successful_episodes']==2


def test_d2_restore_preserves_warmstart_after_forward(monkeypatch):
    import numpy as np
    original_values = np.array([.125, -.25])
    data=SimpleNamespace(qacc_warmstart=original_values.copy())
    wrapper=SimpleNamespace(env=SimpleNamespace(sim=SimpleNamespace(data=data)))
    observation={'rgb':'unchanged'}
    def original_restore(wrapper,saved):
        # The actual MuJoCo CPU reproduction showed forward changes solver input.
        wrapper.env.sim.data.qacc_warmstart[:]=[.12,-.24]
        return observation
    state=SimpleNamespace(restore_actuators=original_restore)
    package=SimpleNamespace(v5_branch_state=state)
    monkeypatch.setitem(sys.modules,'robots.libero',package)
    launcher.install_d2_restore_compatibility()
    assert state.restore_actuators(wrapper,{'data':{'qacc_warmstart':original_values}}) is observation
    assert np.array_equal(data.qacc_warmstart,original_values)
    assert state.restore_actuators.__wrapped__ is original_restore


def test_registered_original_join_excludes_startup_and_rejects_duplicates(tmp_path):
    spec=importlib.util.spec_from_file_location('shared_original_summary',
        _PATH.with_name('summarize_shared_original_20261019.py'))
    summary=importlib.util.module_from_spec(spec);spec.loader.exec_module(summary)
    prep=tmp_path/'preparation';prep.mkdir()
    results=tmp_path/'results';results.mkdir()
    cases=[{'name':'bowl','category':'transfer'},{'name':'drawer','category':'open'}]
    manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps({'cases':cases}))
    def row(index,success):
        return {'case':cases[index],'arm':'oracle_k4','status':'physical_result',
            'pi05_calls':0,'success':success,'failure_phase':None if success else 'contact_failure'}
    old=tmp_path/'old.jsonl';old.write_text(json.dumps(row(0,True))+'\n')
    plan={'selected_n':8,'already_completed':[{'index':0,'record':str(old)}],
        'batches':[{'domain':'original','manifest':{'path':str(manifest),'sha256':launcher.digest(manifest)},
            'source_commit':'pinned','indices':[1]}]}
    plan_path=prep/'batch_plan.json';plan_path.write_text(json.dumps(plan))
    (prep/'full_original_submission.json').write_text(json.dumps({'job':'123','indices':[0]}))
    directory=results/'job123_0/N8/000_drawer';directory.mkdir(parents=True)
    assignment=directory/'assignment.json'
    assignment.write_text(json.dumps({'case_index':1,'case':cases[1],'startup':False}))
    (directory/'worker_summary.json').write_text(json.dumps({'source_commit':'pinned',
        'exit_code':0,'result':row(1,False)}))
    # A separate smoke/study directory must not be scanned into the cohort.
    extra=results/'job999_0/N8/000_bowl';extra.mkdir(parents=True)
    (extra/'worker_summary.json').write_text(json.dumps({'result':row(0,True)}))
    report=summary.summarize(*summary.collect(prep,results))
    assert (report['registered_n'],report['n'],report['success'])==(2,2,1)
    assert report['missing_indices']==[]
    assignment.write_text(json.dumps({'case_index':1,'case':cases[1],'startup':True}))
    with pytest.raises(AssertionError):summary.collect(prep,results)
    assignment.write_text(json.dumps({'case_index':1,'case':cases[1],'startup':False}))
    plan['already_completed'].append({'index':0,'record':str(old)})
    plan_path.write_text(json.dumps(plan))
    with pytest.raises(AssertionError,match='duplicate registered result'):summary.collect(prep,results)


@pytest.mark.parametrize('with_failure',[False,True])
def test_real_subprocesses_isolate_episode_globals_and_retain_failures(tmp_path,with_failure):
    source=tmp_path/'source';source.mkdir()
    for package in ['scripts','rpent','rpent/utils','rpent/utils/rpc']:
        directory=source/package;directory.mkdir(exist_ok=True,parents=True)
        (directory/'__init__.py').write_text('')
    (source/'rpent/utils/rpc/http_rpc.py').write_text('''
class HttpRpcClient:
    def __init__(self, url): self._base_url=url
''')
    (source/'scripts/probe_bounded_feasibility.py').write_text('''
import os
counter=0
def probe_config(base): return base
def episode(case, arm, endpoints, output, config, *, startup):
    global counter
    counter+=1
    assert counter==1, 'episode state leaked'
    assert endpoints['sam3']._base_url=='http://127.0.0.1:1234'
    if case['name']=='fail': raise ValueError('deliberate worker failure')
    return {'status':'physical_result','success':True,'counter':counter,'pid':os.getpid()}
''')
    config=tmp_path/'base.json';config.write_text('{}')
    cases=[{'name':('fail' if with_failure and i==2 else f'case{i}')} for i in range(5)]
    plan={'source_commit':'fixed','cases':cases,'base_config':{'path':str(config),'sha256':launcher.digest(config)}}
    manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps(plan))
    output=tmp_path/'out';output.mkdir()
    args=SimpleNamespace(source=source,manifest=manifest,output=output,domain='original',startup=False)
    sampler=SimpleNamespace(stage=None,summary=lambda _: {'samples':0})
    result=launcher.run_level(args,plan,list(range(5)),{'sam3':SimpleNamespace(_base_url='http://127.0.0.1:1234')},4,sampler)
    rows=[json.loads(line) for line in (output/'N4/episodes.jsonl').read_text().splitlines()]
    assert result['finished_processes']==5 and result['worker_errors']==int(with_failure)
    successful=[row for row in rows if row['process_exit_code']==0]
    assert len({row['pid'] for row in successful})==len(successful)
    assert all(row['result']['counter']==1 for row in successful)
    if with_failure:
        failed,=[row for row in rows if row['process_exit_code']!=0]
        assert failed['exit_code']==1 and failed['error']=='ValueError'
        assert failed['message']=='deliberate worker failure'


@pytest.mark.parametrize('domain',['original','d2'])
def test_batch_preflight_imports_only_pinned_source_and_environment(tmp_path,domain):
    source=tmp_path/'snapshot';source.mkdir()
    (source/'scripts').mkdir();(source/'scripts/__init__.py').write_text('')
    (source/'scripts/probe_bounded_feasibility.py').write_text('''
def services(*a,**kw): raise AssertionError('CPU preflight started a GPU service')
def probe_config(base): return base
''')
    (source/'scripts/v5_probe_preflight.py').write_text('''
import json,os
from pathlib import Path
def load_pinned_manifest(path): return None,json.loads(path.read_bytes()),{}
def validate_registered_states(cases):
    assert Path.cwd()==Path(os.environ['PYTHONPATH'])
    assert os.environ['LIBERO_TYPE'] in ('standard','pro')
    Path(os.environ['PREFLIGHT_OBSERVED']).write_text(json.dumps({
        'cases':cases,'source':str(Path.cwd()),'libero_type':os.environ['LIBERO_TYPE'],
        'source_commit':os.environ['SOURCE_COMMIT']}))
''')
    (source/'robots').mkdir();(source/'robots/__init__.py').write_text('')
    (source/'robots/libero').mkdir();(source/'robots/libero/__init__.py').write_text('')
    (source/'robots/libero/env_server.py').write_text('')
    (source/'robots/libero/bounded_hybrid_diagnostic.py').write_text(
        'def validate_d2_episode(episode): pass\n')
    bddl=tmp_path/'original.bddl';bddl.write_text('registered original scene')
    cases=[{'name':f'case{i}','episode':{'seed':i},
        'bddl':{'path':str(bddl),'sha256':launcher.digest(bddl)}} for i in range(40)]
    manifest=tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'source_commit':'pinned123','cases':cases,
                                   'training':False,'confirmation':False}))
    batch=tmp_path/'batch.json'
    batch.write_text(json.dumps({'selected_n':8,'batches':[{'source':str(source),
        'source_commit':'pinned123','domain':domain,'indices':[2,5],
        'manifest':{'path':str(manifest),'sha256':launcher.digest(manifest)}}]}))
    observed=tmp_path/'observed.json'
    command=[sys.executable,str(_PATH),'--batch-plan',str(batch),'--preflight']
    result=subprocess.run(command,cwd=tmp_path,env={**os.environ,
        'SLURM_ARRAY_TASK_ID':'0','PREFLIGHT_OBSERVED':str(observed)},capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    evidence=json.loads(observed.read_bytes())
    assert evidence=={'cases':[cases[2],cases[5]],'source':str(source),
        'libero_type':'standard' if domain=='original' else 'pro','source_commit':'pinned123'}
    assert json.loads(result.stdout)['levels']==[8]
    # Altering an input after registration must fail before starting services.
    manifest.write_text(manifest.read_text()+' ')
    rejected=subprocess.run(command,cwd=tmp_path,env={**os.environ,
        'SLURM_ARRAY_TASK_ID':'0','PREFLIGHT_OBSERVED':str(observed)},capture_output=True,text=True)
    assert rejected.returncode!=0
