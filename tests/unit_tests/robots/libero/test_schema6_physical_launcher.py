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


@pytest.mark.parametrize('variants', [None, [{'name': 'in_place', 'parameters': {'preparation': 'in_place'}}]])
def test_worker_passes_registered_invocation_groups_into_d2_evaluator(tmp_path, monkeypatch, variants):
    from scripts import probe_bounded_hybrid_d2 as probe

    path = Path(__file__).resolve().parents[4]/'coordination/bounded_skills_20261016/scripts/run_schema6_physical_20261020.py'
    spec = importlib.util.spec_from_file_location('schema6_variant_worker', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    parent = tmp_path/'parent.json'
    parent.write_text(json.dumps({'cases': [{'name': 'D2'}]}))
    case = {'name': 'D2'}
    plan = {'source_commit': 'tested', 'schema_version': 'bounded-skills/6',
        'vla_options_v2': True, 'jobs': [{'kind': 'd2', 'recovery_budget': 1, 'case': case,
            'manifest': {'path': str(parent), 'sha256': hashlib.sha256(parent.read_bytes()).hexdigest()}}]}
    if variants is not None:
        plan['vla_variants'] = variants
    output = tmp_path/'out'
    output.mkdir()
    (output/'assignment.json').write_text(json.dumps({'sam3_url': 'http://127.0.0.1:1', 'vla_url': 'http://127.0.0.1:2'}))
    monkeypatch.setattr(module, 'hooks', lambda _: SimpleNamespace(
        bootstrap_source=lambda *_: None, install_d2_restore_compatibility=lambda: None,
        install_d2_request_compatibility=lambda *_: None))
    received = []
    def evaluate(actual_case, _, __, registered, **kwargs):
        assert actual_case == case and kwargs['startup'] is False
        received.append(registered)
        return {'status': 'physical_result'}
    monkeypatch.setattr(probe, 'evaluate_case', evaluate)
    assert module.worker(SimpleNamespace(source=tmp_path, output=output, worker=0, startup=False), plan) == 0
    assert received[0].get('vla_variants') == variants
    assert received[0]['recovery_budget'] == 1


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


@pytest.mark.parametrize('result,accepted', [
    ({'status': 'physical_result', 'trials': [{'sim_steps': 129}]}, True),
    ({'status': 'startup_physical', 'first_physical': {'receipts': [{'steps_used': 1}]}}, True),
    ({'status': 'physical_result', 'trials': [{'sim_steps': 0}]}, False),
    ({'status': 'startup_physical'}, False),
    ({'status': 'startup_error', 'trials': [{'sim_steps': 129}]}, False),
])
def test_fixed_latency_startup_requires_controls_in_both_report_formats(result, accepted):
    path = Path(__file__).resolve().parents[4] / 'coordination/bounded_skills_20261016/scripts/run_fixed_latency_20261020.py'
    spec = importlib.util.spec_from_file_location('schema6_fixed_latency_startup', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if accepted:
        module.require_physical_startup(result)
    else:
        with pytest.raises(RuntimeError, match='physical request'):
            module.require_physical_startup(result)


def test_n1_common_start_requires_complete_state_and_verifies_each_arm(tmp_path):
    import copy
    import hashlib
    import pickle
    path = Path(__file__).resolve().parents[4] / 'coordination/bounded_skills_20261016/scripts/run_fixed_latency_20261020.py'
    spec = importlib.util.spec_from_file_location('schema6_common_start',path)
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    physical = {'actuator_state':{'integration':{'sha256':'complete-vector'}},'rng':17}
    current = copy.deepcopy(physical)
    adapter=SimpleNamespace(source='baseline',refresh_count=0, _incremental_previous_robot={'stale':True})
    def refresh():
        assert adapter._incremental_previous_robot is None
        adapter.refresh_count+=1
    adapter.refresh=refresh
    facade = SimpleNamespace(snapshot=lambda:copy.deepcopy(current))
    def save(facade,adapter,policy,destination):
        destination.write_bytes(pickle.dumps({'physics':facade.snapshot()}))
    def restore(facade,adapter,policy,saved):
        current.clear();current.update(copy.deepcopy(saved['physics']))
        adapter.source='inherited-baseline-cache'
    digest=lambda value:hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
    probe=SimpleNamespace(save_checkpoint=save,restore_checkpoint=restore,snapshot_digest=digest,
        capture_runtime=lambda adapter,policy:adapter.source,
        restore_runtime=lambda adapter,policy,source:setattr(adapter,'source',source))
    args=SimpleNamespace(common_starts=tmp_path/'common',worker=0,startup=False,
        initial_mode='create',output=tmp_path/'baseline')
    args.output.mkdir()
    baseline=module.common_start(args,facade,adapter,None,probe)
    assert adapter.source=='baseline' and adapter.refresh_count==1
    current['rng']=999
    adapter.source='optimized'
    adapter._incremental_previous_robot={'stale':True}
    args.initial_mode='restore';args.output=tmp_path/'optimized';args.output.mkdir()
    optimized=module.common_start(args,facade,adapter,None,probe)
    assert current==physical
    assert adapter.source=='optimized' and adapter.refresh_count==2
    assert baseline['actual_complete_initial_sha256']==optimized['actual_complete_initial_sha256']
    probe.restore_checkpoint=lambda *_:None
    current['rng']=123
    args.output=tmp_path/'mismatched';args.output.mkdir()
    with pytest.raises(ValueError,match='initial state differs'):
        module.common_start(args,facade,adapter,None,probe)
