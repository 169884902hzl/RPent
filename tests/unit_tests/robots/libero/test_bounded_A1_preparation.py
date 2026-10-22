"""The diagnostic replays recorded primitives and retains actual controls."""
from types import SimpleNamespace

from scripts.probe_bounded_A1_preparation import motion_commands, execute_motion


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
