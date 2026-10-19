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
