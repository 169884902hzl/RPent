"""The original heldout probe uses the real service's decision boundary."""
from contextlib import contextmanager
import json
from types import SimpleNamespace

import pytest

from coordination.bounded_skills_20261016.scripts import original_model_closedloop_20261021 as module
from robots.libero.bounded_timing import EpisodeTimings


def test_health_rejects_a_different_checkpoint_even_when_ready(monkeypatch):
    from io import StringIO
    monkeypatch.setattr(module, 'urlopen', lambda *_args, **_kwargs: StringIO(json.dumps({
        'status': 'ok', 'adapter_sha256': 'different'})))
    with pytest.raises(ValueError, match='adapter differs'):
        module.verified_health({'health_url': 'offline', 'adapter_sha256': 'registered'})


@pytest.mark.parametrize('startup,decisions,steps', [(False, 2, 7), (True, 1, 7)])
def test_http_choices_execute_and_stop_without_oracle_selection(tmp_path, monkeypatch, startup, decisions, steps):
    env = SimpleNamespace(terminated=False, truncated=False)
    requests = []
    adapter = SimpleNamespace(p=SimpleNamespace(env=env), details=[])
    def request(*, k):
        assert k == 4 and adapter.allow_vla and adapter.vla_options_v2
        return {'id': len(requests), 'public_only': True}
    adapter.request = request
    def execute(actual, decision):
        assert decision['candidate_ids'] == ['http-'+str(actual['id'])]
        return [{'skill': 'move_to' if len(requests) == 1 else 'finish',
            'steps_used': 7 if len(requests) == 1 else 0}]
    adapter.execute = execute
    def choose(actual):
        requests.append(actual)
        return {'candidate_ids': ['http-'+str(actual['id'])]}
    monkeypatch.setattr('robots.libero.bounded_async.http_choice', lambda endpoint: choose)
    monkeypatch.setattr(module, 'verified_health', lambda _: {'status': 'ok'})
    @contextmanager
    def runtime(*_args, **kwargs):
        assert kwargs['domain'] == 'original'
        # Any accidental policy.choose call fails: there is no oracle here.
        yield SimpleNamespace(goal_status=lambda: {'done': True}), adapter, object(), EpisodeTimings()
    probe = SimpleNamespace(runtime=runtime,
        save_checkpoint=lambda *_: (None, {'path': 'initial', 'sha256': 'saved'}))
    plan = {'model_service': {'endpoint': 'offline'}, 'source_commit': 'tested',
        'runtime_budget': {'decisions': 160}}
    output = tmp_path/'episode'
    result = module.run_episode(probe, {'name': 'heldout'}, {}, output, plan, 4, startup=startup)
    assert (result['decisions'], result['sim_steps']) == (decisions, steps)
    assert result['oracle_choices_used'] == 0 and result['split'] == 'init_holdout'
    assert result['selected_option_ids'] == [['http-'+str(i)] for i in range(decisions)]
    rows = [json.loads(line) for line in (output/'choices.jsonl').read_text().splitlines()]
    assert all(row['wall_time_breakdown']['oracle_successor_legal_s'] == 0 for row in rows)
    assert len(rows) == decisions
