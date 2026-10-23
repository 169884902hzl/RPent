"""Persistent loops retain a failed world until a registered budget ends."""
import importlib.util
import json
import pickle
from pathlib import Path
from types import SimpleNamespace


def test_native_query_targets_the_inner_libero_environment():
    from robots.libero.bounded_success_loop import native_success
    calls=[]
    worker=SimpleNamespace(env_call=lambda name:calls.append(name) or True)
    facade=SimpleNamespace(_env=SimpleNamespace(env=SimpleNamespace(workers=[worker])))
    assert native_success(facade) and calls==['_check_success']


def test_forty_failures_do_not_consume_a_recovery_stop(tmp_path, monkeypatch):
    import robots.libero.bounded_success_loop as loop
    entry = Path(__file__).resolve().parents[4]/'coordination/bounded_skills_20261016/scripts/run_success_feedback_20261024.py'
    spec = importlib.util.spec_from_file_location('persistent_loop_probe_test', entry)
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    saved = tmp_path/'start.pkl'; saved.write_bytes(pickle.dumps({'physics':{'unchanged':True}}))
    count = {'decisions':0}
    env = SimpleNamespace(terminated=False,truncated=False,execution_budget=lambda:{'used_sim_steps':0,'remaining_sim_steps':10000})
    adapter = SimpleNamespace(p=SimpleNamespace(env=env,model=None),details=[],
        request=lambda **_: {'feedback':{'task_success':True,'subgoal_status':False},'task_success':False},
        success_feedback=SimpleNamespace(reads=40))
    def execute(request,decision):
        count['decisions']+=1
        return [{'outcome':'failure','steps_used':0,'stop_reason':'blocked'}]
    adapter.execute=execute
    monkeypatch.setattr(loop,'enable',lambda *_,**__:None)
    monkeypatch.setattr(loop,'native_success',lambda _:False)
    monkeypatch.setattr(loop,'choose',lambda *_,**__:({'candidate_ids':['existing']},{}))
    facade=SimpleNamespace(snapshot=lambda:{'unchanged':True})
    probe=SimpleNamespace(restore_checkpoint=lambda *a:None,snapshot_digest=lambda _: 'same',
        SeededPolicy=lambda *a,**k:SimpleNamespace(calls=0))
    row={'initial_snapshot':module.reference(saved),'arm':'oracle_A','policy_seed':1,
         'k':4,'case':{'name':'fixture'},'domain':'original','arm_id':'fixture_K4'}
    args=SimpleNamespace(output=tmp_path)
    result=module.run_episode(args,{'vla_budget':{},'source_commit':'pinned'},row,probe,facade,adapter,None,None)
    assert count['decisions']==result['decisions']==40
    assert result['stop_reason']=='decision_budget' and not result['success']
    assert len((tmp_path/'choices.jsonl').read_text().splitlines())==40
