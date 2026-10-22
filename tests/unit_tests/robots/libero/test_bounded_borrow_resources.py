"""A borrowed running array task is returned without touching other jobs."""
import json

from coordination.bounded_skills_20261016.scripts.watch_B2_resources_20261021 import release_candidate


def test_borrowed_array_task_is_selected_on_either_c2_job_prefix():
    ours = [[f'11403_{i}', 'rd-c3-s6-B2-groups-labels', 'RUNNING', 'node02', 'gres/gpu:1', 'None']
        for i in range(4)]
    for prefix in ('rd-c2-', 'rd-bounded-choice-'):
        c2 = ['11404', prefix + 'epoch', 'PENDING', '', 'gres/gpu:1', 'Resources']
        selected, running, demand = release_candidate(ours + [c2], ['11403_3'])
        assert selected == '11403_3' and len(running) == 4 and demand == ['11404']
    held = ['11404', 'rd-c2-epoch', 'PENDING', '', 'gres/gpu:1', 'JobHeldUser']
    assert release_candidate(ours + [held], ['11403_3'])[0] is None


def test_other_projects_and_unregistered_tasks_cannot_be_returned():
    rows = [[str(i), name, 'RUNNING', 'node02', 'gres/gpu:1', 'None']
        for i, name in enumerate(('c5-other', 'rf-other', 'p3-other', 'rd-c3-unregistered'))]
    rows.append(['11404', 'rd-c2-epoch', 'PENDING', '', 'gres/gpu:1', 'Resources'])
    assert release_candidate(rows, ['0', '1', '2', '3'])[0] is None


def test_main_accepts_array_ids_and_sends_the_owned_cancellation(tmp_path, monkeypatch):
    from coordination.bounded_skills_20261016.scripts import watch_B2_resources_20261021 as watch
    jobs, ledger = tmp_path / 'jobs.json', tmp_path / 'events.jsonl'
    jobs.write_text(json.dumps({'prefer_release': ['11403_1']}))
    rows = [f'11403_{i}|rd-c3-s6-B2-groups-labels|RUNNING|node02|gres/gpu:1|None'
        for i in range(4)]
    rows.append('11404|rd-c2-epoch|PENDING||gres/gpu:1|Resources')
    commands = []
    def remote(command, **kwargs):
        commands.append(command[-1])
        if command[-1].startswith('squeue'):
            return '\n'.join(rows) if len(commands) == 1 else ''
        assert command[-1] == 'scancel 11403_1'
        return ''
    monkeypatch.setattr('sys.argv', ['watch', '--jobs', str(jobs), '--ledger', str(ledger)])
    monkeypatch.setattr(watch.subprocess, 'check_output', remote)
    monkeypatch.setattr(watch.time, 'sleep', lambda *_: None)
    watch.main()
    events = [json.loads(l) for l in ledger.read_text().splitlines()]
    assert events[0]['action'] == 'cancel_running_resumable_owned_shard'
    assert events[0]['job'] == '11403_1' and events[-1]['done']
