"""Preserve startup admission and completed checkpoints with shared services."""
import hashlib
import importlib.util
import json
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest


def setup_launcher(tmp_path, monkeypatch, *, fail_startup=False):
    path = Path(__file__).resolve().parents[4] / 'coordination/bounded_skills_20261016/scripts/run_schema6_physical_20261020.py'
    spec = importlib.util.spec_from_file_location('schema6_physical_launcher', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    entry = tmp_path / 'sam.py'
    entry.write_text('# fake service entry\n')
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps({'training': False, 'schema_version': 'bounded-skills/6',
        'source_commit': 'test', 'jobs': [{'case': {}} for _ in range(9)],
        'sam_entry': {'path': str(entry), 'sha256': hashlib.sha256(entry.read_bytes()).hexdigest()}}))
    output = tmp_path / 'output'
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'path', sys.path.copy())
    monkeypatch.setattr(sys, 'argv', ['launcher', '--source', str(tmp_path), '--manifest', str(manifest),
        '--output', str(output), '--episode-concurrency', '3'])

    @contextmanager
    def services(*_, **__):
        yield {'sam3': SimpleNamespace(_base_url='private_sam'), 'vla': SimpleNamespace(_base_url='private_vla')}

    monkeypatch.setitem(sys.modules, 'scripts.probe_bounded_feasibility', SimpleNamespace(services=object()))
    monkeypatch.setattr(module, 'hooks', lambda _: SimpleNamespace(
        bootstrap_source=lambda *_: None, owned_services=services))
    stats = {'active': 0, 'peak': 0, 'formal': [], 'startup': 0}
    lock = threading.Lock()

    def run(command, **_):
        if '--startup' in command:
            stats['startup'] += 1
            if fail_startup:
                raise subprocess.CalledProcessError(1, command)
        else:
            with lock:
                assert stats['startup'] > 0
                stats['active'] += 1
                stats['peak'] = max(stats['peak'], stats['active'])
                stats['formal'].append(int(command[command.index('--worker') + 1]))
            time.sleep(.03)
            with lock:
                stats['active'] -= 1
        directory = Path(command[command.index('--output') + 1])
        (directory / 'summary.json').write_text(json.dumps({'status': 'physical_result'}))

    monkeypatch.setattr(module.subprocess, 'run', run)
    return module, output, stats


def test_real_startup_precedes_pool_and_closed_cases_are_not_repeated(tmp_path, monkeypatch):
    module, output, stats = setup_launcher(tmp_path, monkeypatch)
    assert module.main() == 0
    assert stats['peak'] == 3 and sorted(stats['formal']) == list(range(9))
    pointers = list(output.glob('closed_*.json'))
    assert len(pointers) == 9
    for path in pointers:
        row = json.loads(path.read_bytes())
        assert row['sha256'] == hashlib.sha256(Path(row['summary']).read_bytes()).hexdigest()
    assert module.main() == 0
    assert stats['startup'] == 1 and len(stats['formal']) == 9


def test_failed_startup_raises_before_dispatching_any_full_case(tmp_path, monkeypatch):
    module, output, stats = setup_launcher(tmp_path, monkeypatch, fail_startup=True)
    with pytest.raises(subprocess.CalledProcessError):
        module.main()
    assert stats['formal'] == [] and not list(output.glob('closed_*.json'))


def test_n1_resume_preserves_completed_cases_and_interrupted_attempt(tmp_path):
    path = Path(__file__).resolve().parents[4] / 'coordination/bounded_skills_20261016/scripts/run_fixed_latency_20261020.py'
    spec = importlib.util.spec_from_file_location('schema6_fixed_latency', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    complete = tmp_path / 'case000'
    complete.mkdir()
    summary = complete / 'summary.json'
    summary.write_text(json.dumps({'status': 'physical_result', 'success': False}))
    interrupted = tmp_path / 'case001'
    interrupted.mkdir()
    (interrupted / 'worker.log').write_text('interrupted physical attempt')
    pending = module.pending_cases(tmp_path, [0, 1, 2])
    assert pending == [(1, tmp_path / 'case001_attempt1'), (2, tmp_path / 'case002')]
    assert (interrupted / 'worker.log').read_text() == 'interrupted physical attempt'
    assert (tmp_path / 'closed_000.json').exists()
    summary.write_text('changed')
    with pytest.raises(ValueError):
        module.pending_cases(tmp_path, [0])


def test_move_outcome_tracks_parent_goal_and_held_transfer_stage(tmp_path, monkeypatch):
    module, _, _ = setup_launcher(tmp_path, monkeypatch)
    cabinet = SimpleNamespace(id='cabinet', part_of=None)
    panel = SimpleNamespace(id='door', part_of='cabinet')
    obj = SimpleNamespace(id='object', part_of=None)
    adapter = SimpleNamespace(scene=SimpleNamespace(entities={
        'cabinet': cabinet, 'door': panel, 'object': obj}), held=None)
    facade = SimpleNamespace(goal_status=lambda: {'satisfied': [False]})
    close = {'goal_index': 0, 'mode': 'close'}
    bindings = SimpleNamespace(bind_subtask=lambda *args: (cabinet, None))
    assert module.move_subtask(bindings, facade, adapter, None, [close], 'door') == close
    assert module.move_subtask(bindings, facade, adapter, None, [close], 'object') is None

    pick = {'goal_index': 0, 'mode': 'pick'}
    place = {'goal_index': 0, 'mode': 'in'}
    adapter.held = obj.id
    bindings.bind_subtask = lambda *args: (obj, cabinet)
    assert module.move_subtask(bindings, facade, adapter, None, [pick, place], 'cabinet') == place
    assert module.move_subtask(bindings, facade, adapter, None, [pick, place], 'object') == place
