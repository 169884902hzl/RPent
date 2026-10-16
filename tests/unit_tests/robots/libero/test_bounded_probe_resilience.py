"""A startup failure is preserved and only its state gets one marked retry."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.probe_bounded_feasibility import legacy_episode


def test_legacy_infrastructure_retry_retains_first_log(tmp_path, monkeypatch):
    calls = []
    def run(command, **kwargs):
        payload = json.loads(Path(command[-1]).read_text())
        output = Path(payload['output'])
        calls.append(output)
        if len(calls) == 1:
            (output/'legacy').mkdir()
            (output/'legacy/result.json').write_text(json.dumps({'infrastructure_failure': True,
                'error': 'env.reset timed out', 'decisions': 0}))
            return SimpleNamespace(returncode=1, args=command)
        (output/'legacy_result.json').write_text(json.dumps({'legacy_result': {'official_success': False,
            'decisions': 3, 'wall_s': 1., 'termination_category': 'no_legal_candidate'},
            'public_execution_budget': {'used_sim_steps': 100}, 'source_files': []}))
        return SimpleNamespace(returncode=0, args=command)
    monkeypatch.setattr('scripts.probe_bounded_feasibility.subprocess.run', run)
    endpoints = {k: SimpleNamespace(_base_url='http://localhost') for k in ('sam3','vla')}
    output = tmp_path/'trial'
    result = legacy_episode({'name': 'case'}, endpoints, output, {}, tmp_path)
    assert len(calls) == 2
    assert result['status'] == 'physical_result' and result['success'] is False
    assert result['sim_steps'] == 100
    assert (output/'legacy/result.json').is_file()
    assert result['infrastructure_attempts'][0]['physical_decisions'] == 0
    assert (output/'infrastructure_retry1/legacy_worker.log').is_file()


@pytest.mark.parametrize('suite', ['libero_spatial', 'libero_90'])
def test_legacy_admission_matches_client_and_server_metadata(tmp_path, monkeypatch, suite):
    from scripts import probe_bounded_legacy_worker as worker

    source = tmp_path/'source'
    for name in ('harness_v5_eval.py', 'robots/libero/v5_runtime.py',
                 'robots/libero/v5_state.py', 'robots/libero/v5_oracle_policy.py'):
        path = source/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# pinned historical source\n')
    seen = []
    def run_episode(args):
        seen.append(args)
        return {'official_success': True, 'decisions': 1}
    harness = SimpleNamespace(__file__=str(source/'harness_v5_eval.py'), run_episode=run_episode)
    client = type('Client', (), {'_TIMEOUT_S': {}, 'step': lambda *a: None, 'chunk_step': lambda *a: None})
    monkeypatch.setitem(sys.modules, 'harness_v5_eval', harness)
    monkeypatch.setitem(sys.modules, 'robots.libero.env_client', SimpleNamespace(LiberoEnvClient=client))
    output = tmp_path/'output'
    output.mkdir()
    payload = tmp_path/'payload.json'
    payload.write_text(json.dumps({'source': str(source), 'output': str(output),
        'budget': {'max_episode_steps': 10000}, 'case': {'episode': {'suite': suite, 'task': 0, 'seed': 0}},
        'allow_original90_adapter': suite == 'libero_90', 'choice_package': str(tmp_path),
        'sam3_endpoint': 'http://localhost:1', 'vla_endpoint': 'http://localhost:2'}))
    monkeypatch.setattr(sys, 'argv', ['worker', '--payload', str(payload)])
    worker.main()
    assert getattr(seen[0], 'original90_grasp_diagnostic_v1', False) == (suite == 'libero_90')
    result = json.loads((output/'legacy_result.json').read_text())
    assert result['original90_diagnostic_admission_adapter'] == (suite == 'libero_90')


def test_bounded_queries_depend_only_on_instruction_and_static_labels():
    from scripts.probe_bounded_feasibility import public_vocabulary

    assert set(public_vocabulary('pick up the black bowl between the plate and the ramekin and place it on the plate')) == {'bowl', 'plate', 'ramekin'}
    assert {'drawer', 'cabinet'} <= set(public_vocabulary('close the top drawer of the cabinet'))
    assert 'frypan' in public_vocabulary('put the frying pan on the stove')
    assert 'wine bottle' not in public_vocabulary('pick up the bowl')


def test_forks_use_identical_full_snapshot_without_sharing_branch_results(tmp_path):
    import hashlib
    import pickle
    from scripts.probe_bounded_forks import run_pair

    saved = {'sim_state': [1., 2.], 'actuator_state': {'rng': [17]}, 'counters': {'steps': 0}}
    closed, seen = [], []
    facade = SimpleNamespace(snapshot=lambda: saved, close=lambda: closed.append(True))
    def run(case, arm, endpoints, output, config, *, initial_snapshot, pick_branch):
        assert pick_branch and initial_snapshot == saved
        seen.append((arm, output, initial_snapshot))
        return {'success': False, 'subtask_private_success': arm == 'oracle_k4'}
    result = run_pair({'episode': {'suite': 'libero_spatial', 'task': 0, 'seed': 0}}, {},
        tmp_path/'pair', {}, session=lambda *args: (facade, None), run=run)
    raw = Path(result['snapshot']['path']).read_bytes()
    assert result['snapshot']['sha256'] == hashlib.sha256(raw).hexdigest()
    assert pickle.loads(raw) == saved
    assert closed == [True] and len(seen) == 2
    assert seen[0][1] != seen[1][1]
    assert [row['result']['subtask_private_success'] for row in result['branches']] == [True, False]
    assert result['training_admission'] is False
