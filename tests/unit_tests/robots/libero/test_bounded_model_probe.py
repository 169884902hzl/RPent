"""The original heldout probe uses the real service's decision boundary."""
from contextlib import contextmanager
import json
from types import SimpleNamespace

import pytest

from coordination.bounded_skills_20261016.scripts import original_model_closedloop_20261021 as module
from robots.libero.bounded_timing import EpisodeTimings


@pytest.mark.parametrize('row,expected', [
    ({'kind': 'model', 'split': 'd2_evaluation'}, 'pro'),
    ({'kind': 'model', 'split': 'init_holdout'}, 'standard'),
    ({'kind': 'd2'}, 'pro'),
    ({'kind': 'd2_replay'}, 'pro'),
    ({'kind': 'original_fork'}, 'standard'),
    ({'kind': 'smoke'}, 'standard'),
])
def test_worker_selects_registered_domain_before_simulator_import(tmp_path, monkeypatch, row, expected):
    import os
    from coordination.bounded_skills_20261016.scripts import run_schema6_physical_20261020 as launcher

    class BootstrapObserved(Exception):
        pass

    def bootstrap(_domain):
        assert os.environ['LIBERO_TYPE'] == expected
        raise BootstrapObserved

    monkeypatch.setattr(launcher, 'hooks', lambda _: SimpleNamespace(bootstrap_source=bootstrap))
    with pytest.raises(BootstrapObserved):
        launcher.worker(SimpleNamespace(worker=0, source=tmp_path, output=tmp_path), {'jobs': [row]})


def test_health_rejects_a_different_checkpoint_even_when_ready(monkeypatch):
    from io import StringIO
    monkeypatch.setattr(module, 'urlopen', lambda *_args, **_kwargs: StringIO(json.dumps({
        'status': 'ok', 'adapter_sha256': 'different'})))
    with pytest.raises(ValueError, match='adapter differs'):
        module.verified_health({'health_url': 'offline', 'adapter_sha256': 'registered'})


@pytest.mark.parametrize('startup,decisions,steps,reject', [(False, 2, 7, False), (True, 1, 7, False),
    (False, 0, 0, True)])
@pytest.mark.parametrize('first_skill', ['move_to', 'ask_help'])
@pytest.mark.parametrize('domain,split', [('original', 'init_holdout'), ('d2', 'd2_evaluation')])
def test_http_choices_execute_and_stop_without_oracle_selection(tmp_path, monkeypatch, startup, decisions, steps, reject, first_skill, domain, split):
    env = SimpleNamespace(terminated=False, truncated=False)
    requests = []
    adapter = SimpleNamespace(p=SimpleNamespace(env=env, model=object()), details=[])
    def request(*, k):
        assert k == 4 and adapter.allow_vla and adapter.vla_options_v2
        return {'id': len(requests), 'public_only': True, 'candidates': []}
    adapter.request = request
    def execute(actual, decision):
        assert decision['candidate_ids'] == ['http-'+str(actual['id'])]
        return [{'skill': first_skill if len(requests) == 1 else 'finish',
            'outcome': 'interrupted' if len(requests) == 1 and first_skill == 'ask_help' else 'success',
            'steps_used': 7 if len(requests) == 1 else 0}]
    adapter.execute = execute
    def choose(actual):
        requests.append(actual)
        if reject:
            from io import BytesIO
            from urllib.error import HTTPError
            raise HTTPError('offline', 422, 'Unprocessable Entity', None,
                BytesIO(b'{"detail":"source request rejected"}'))
        return {'candidate_ids': ['http-'+str(actual['id'])]}
    monkeypatch.setattr('robots.libero.bounded_async.http_choice', lambda endpoint, **_: choose)
    monkeypatch.setattr(module, 'verified_health', lambda _: {'status': 'ok'})
    @contextmanager
    def runtime(*_args, **kwargs):
        assert kwargs['domain'] == domain
        # Any accidental policy.choose call fails: there is no oracle here.
        yield SimpleNamespace(goal_status=lambda: {'done': True}), adapter, object(), EpisodeTimings()
    probe = SimpleNamespace(runtime=runtime,
        save_checkpoint=lambda *_: (None, {'path': 'initial', 'sha256': 'saved'}))
    plan = {'model_service': {'endpoint': 'offline'}, 'source_commit': 'tested',
        'runtime_budget': {'decisions': 160}}
    output = tmp_path/'episode'
    if reject:
        with pytest.raises(RuntimeError, match='model HTTP 422.*source request rejected'):
            module.run_episode(probe, {'name': 'heldout'}, {}, output, plan, 4, domain=domain, split=split)
        saved = json.loads((output/'model_http_error.json').read_text())
        assert saved['status'] == 422 and json.loads(saved['body'])['detail'] == 'source request rejected'
        sent = [json.loads(x) for x in (output/'requests.jsonl').read_text().splitlines()]
        assert len(sent) == 1 and sent[0]['request'] == requests[0]
        assert sent[0]['model_request'] == requests[0]
        assert saved['model_request_sha256'] == sent[0]['model_request_sha256']
        assert (output/'choices.jsonl').read_text() == ''
        return
    result = module.run_episode(probe, {'name': 'heldout'}, {}, output, plan, 4, startup=startup, domain=domain, split=split)
    assert (result['decisions'], result['sim_steps']) == (decisions, steps)
    assert result['oracle_choices_used'] == 0 and result['split'] == split
    assert result['stop_reason'] == ('startup_physical' if startup else 'finish')
    assert result['selected_option_ids'] == [['http-'+str(i)] for i in range(decisions)]
    rows = [json.loads(line) for line in (output/'choices.jsonl').read_text().splitlines()]
    assert all(row['wall_time_breakdown']['oracle_successor_legal_s'] == 0 for row in rows)
    assert len(rows) == decisions
    assert len((output/'requests.jsonl').read_text().splitlines()) == decisions


def test_shared_vla_service_gets_independent_reproducible_episode_seeds(tmp_path, monkeypatch):
    import numpy as np

    seeds = []
    client = SimpleNamespace(encode_obs=lambda _: {'states': np.zeros(1, np.float32)})
    def predict(_obs, *, options):
        seeds.append(options['sampling_seed'])
        return np.full((5, 7), options['sampling_seed'] % 31, np.float32)
    client.predict = predict
    monkeypatch.setattr(module, 'verified_health', lambda _: {'status': 'ok'})
    def http_choice(endpoint, *, on_response):
        def choose(_request):
            decision = {'candidate_ids': ['http-selected']}
            on_response({'decision': decision, 'actual_service_result': True})
            return decision
        return choose
    monkeypatch.setattr('robots.libero.bounded_async.http_choice', http_choice)

    @contextmanager
    def runtime(*_args, **_kwargs):
        adapter = SimpleNamespace(details=[], held=None,
            p=SimpleNamespace(model=client, env=SimpleNamespace(terminated=False, truncated=False)),
            request=lambda **_: {'max_actions': 4, 'candidates': []})
        def execute(_request, _decision):
            adapter.p.model.predict({'states': np.zeros(1)})
            return [{'skill': 'finish', 'steps_used': 1, 'outcome': 'success'}]
        adapter.execute = execute
        yield SimpleNamespace(goal_status=lambda: {'done': True}), adapter, object(), EpisodeTimings()
        assert adapter.p.model is client

    probe = SimpleNamespace(runtime=runtime, save_checkpoint=lambda *_: (None, {}))
    plan = {'model_service': {'endpoint': 'offline'}, 'source_commit': 'tested',
        'runtime_budget': {'decisions': 2}, 'policy_seed_base': 50000000}
    results = [module.run_episode(probe, {'name': name}, {}, tmp_path/str(i), plan, 4)
        for i, name in enumerate(('episode-a', 'episode-b', 'episode-a'))]
    assert seeds[0] == seeds[2] and seeds[0] != seeds[1]
    assert seeds == [r['vla_policy_seed'] for r in results]
    assert all(r['oracle_choices_used'] == 0 and r['vla_inference_calls'] == 1 for r in results)
    assert results[0]['vla_predictions'] == results[2]['vla_predictions']
    for i in range(3):
        assert json.loads((tmp_path/str(i)/'model_responses.jsonl').read_text())['actual_service_result']
        assert json.loads((tmp_path/str(i)/'vla_inputs.jsonl').read_text())['sampling_seed'] == seeds[i]


def test_health_selects_the_registered_supported_schema_not_the_default(monkeypatch):
    from io import StringIO
    health = {'status': 'ok', 'adapter_sha256': 'registered',
        'skill_package': {'schema_sha256': 'wrong6', 'contract_sha256': 'wrong6'},
        'bounded_supported_schemas': {'bounded-skills/7': {
            'schema_sha256': 'seven', 'contract_sha256': 'legal5'}}}
    monkeypatch.setattr(module, 'urlopen', lambda *_args, **_kwargs: StringIO(json.dumps(health)))
    service = {'health_url': 'offline', 'adapter_sha256': 'registered',
        'schema_version': 'bounded-skills/7', 'schema_sha256': 'seven', 'contract_sha256': 'legal5'}
    assert module.verified_health(service) == health
    service['schema_version'] = 'bounded-skills/8'
    with pytest.raises(ValueError, match='does not support'):
        module.verified_health(service)
