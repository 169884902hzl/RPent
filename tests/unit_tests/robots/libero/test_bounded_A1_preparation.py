"""The diagnostic replays recorded primitives and retains actual controls."""
from types import SimpleNamespace

from scripts.probe_bounded_A1_preparation import motion_commands, execute_motion


def test_combination_scopes_scripts_around_the_selected_subtask():
    from scripts.probe_bounded_A1_preparation import combination_commands
    calls = [{'ordinal': 1, 'tool': 'move_to', 'parameters': {'xyz': [0, 0, 1]}},
        {'ordinal': 2, 'tool': 'pi0_pick', 'parameters': {'prompt': 'earlier task'}},
        {'ordinal': 3, 'tool': 'move_to', 'parameters': {'xyz': [1, 0, 1]}},
        {'ordinal': 4, 'tool': 'pi0_pick', 'parameters': {'prompt': 'selected task'}},
        {'ordinal': 5, 'tool': 'release', 'parameters': {}},
        {'ordinal': 6, 'tool': 'pi0_doubled', 'parameters': {'prompt': 'later task'}},
        {'ordinal': 7, 'tool': 'move_to', 'parameters': {'xyz': [2, 0, 1]}}]
    pre, tail = combination_commands(calls, 4)
    assert pre == [{key: calls[2][key] for key in ('tool', 'parameters')}]
    assert tail == [{'tool': 'release', 'parameters': {}}]


def test_combination_transports_after_policy_failure_and_restores_endpoint(tmp_path, monkeypatch):
    from contextlib import nullcontext
    from scripts import probe_bounded_A1_preparation as module
    events, prompt = [], []
    client = object()
    primitive = SimpleNamespace(model=client,
        env=SimpleNamespace(execution_budget=lambda: {'used_sim_steps': len(events)}))
    adapter = SimpleNamespace(p=primitive, scene=SimpleNamespace(entities={}),
        _incremental_touched=set(), refresh=lambda: events.append('refresh'),
        request=lambda **_: {})
    monkeypatch.setattr(module, 'execute_motion', lambda _p, commands:
        events.append(commands[0]['tool']) or {'steps_used': 1})
    def trial(*args, **_kwargs):
        assert isinstance(adapter.p.model, module.PromptOverride)
        prompt.append(adapter.p.model.prompt)
        events.append('policy_failed')
        return {'success': False, 'vla_inference_calls': 1}, {'saved': 'before_metrology'}
    monkeypatch.setattr(module.probe, 'trial', trial)
    monkeypatch.setattr(module.probe, 'restore_checkpoint', lambda *_: events.append('restore_endpoint'))
    monkeypatch.setattr(module.probe, 'save_checkpoint', lambda *_: (None, {'path': 'final'}))
    monkeypatch.setattr(module, 'private_score', lambda *_: {
        'private_subtask_success': False, 'native_task_success': True})
    row = {'subtask': {'mode': 'on', 'source_symbol': 'bowl'}, 'a1_pi_ordinal': 2,
        'a1_pi': {'parameters': {'prompt': 'recorded local phrase'}},
        'a1_physical_commands': [{'ordinal': 1, 'tool': 'move_to', 'parameters': {}},
            {'ordinal': 2, 'tool': 'pi0_pick', 'parameters': {}},
            {'ordinal': 3, 'tool': 'release', 'parameters': {}}]}
    result = module.combination_trial(object(), adapter, object(),
        SimpleNamespace(measure=lambda *_: nullcontext()), row, tmp_path, 'combination', 10)
    assert events == ['move_to', 'refresh', 'policy_failed', 'restore_endpoint', 'release']
    assert prompt == ['recorded local phrase'] and adapter.p.model is client
    assert result['policy_reported_success'] is False and result['native_task_success'] is True


def test_staging_and_tail_never_execute_a_later_policy_call_or_a_file_tool():
    calls=[{'tool':'read_text_file','parameters':{'path':'memory'}},
        {'tool':'move_to','parameters':{'xyz':[0,0,1]}},
        {'tool':'pi0_pick','parameters':{'prompt':'source'}},
        {'tool':'release','parameters':{}},
        {'tool':'pi0_doubled','parameters':{'prompt':'target'}}]
    assert motion_commands(calls)==[calls[1]]
    assert motion_commands(calls,tail=True)==[calls[3]]
    selected=motion_commands(calls);selected[0]['parameters']['xyz'][2]=2
    assert calls[1]['parameters']['xyz']==[0,0,1]


def test_raw_motion_records_every_control_and_restores_the_original_step(monkeypatch):
    from robots.libero import bounded_motion
    steps=[]
    primitive=SimpleNamespace(env=SimpleNamespace(terminated=False,truncated=False),
        _step_env=lambda action:steps.append(action))
    original=primitive._step_env
    def move_to(**_):
        for _ in range(3):primitive._step_env([0]*7)
        return {'steps_used':3}
    primitive.move_to=move_to
    monkeypatch.setattr(bounded_motion,'measured_robot',lambda _:{'counter':len(steps)})
    result=execute_motion(primitive,[{'tool':'move_to','parameters':{}}])
    assert result['steps_used']==3 and len(steps)==3
    assert [r['before']['counter'] for r in result['trace']]==[0,1,2]
    assert [r['after']['counter'] for r in result['trace']]==[1,2,3]
    assert primitive._step_env is original
