"""A startup failure is preserved and only its state gets one marked retry."""
import json
from pathlib import Path
from types import SimpleNamespace
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
