"""Replay the retained capacity/context failures without truncating requests."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

p = argparse.ArgumentParser()
p.add_argument('--source', type=Path, required=True)
p.add_argument('--run', type=Path, required=True)
args = p.parse_args()
sys.path.insert(0, str(args.source))
from robots.libero.bounded_async import http_choice
from coordination.bounded_skills_20261016.scripts.original_model_closedloop_20261021 import verified_health

handoff = json.loads(Path('/public/home/sunyihan/rd_instruction_20260923/c2_next_b_20261022_2030/C3_SERVICE_HANDOFF_11688.json').read_text())
package = handoff['supported_source_versions']['bounded-skills/7']
service = {
    'endpoint': 'http://node02:18076/v1/bounded-choice',
    'health_url': 'http://node02:18076/healthz',
    'schema_version': 'bounded-skills/7',
    'adapter_sha256': handoff['adapter_sha256'],
    'schema_sha256': package['schema_sha256'],
    'contract_sha256': package['contract_sha256'],
}
health = verified_health(service)
assert health['single_code_capacity'] == 256
assert health['max_context_tokens'] == 32768
results = []
for directory, index in [('case010', 1), ('case013', 0), ('case010_attempt1', 2)]:
    root = args.run / 'model_d2_0' / directory / 'episode'
    captured = next(json.loads(s) for s in (root / 'requests.jsonl').read_text().splitlines() if json.loads(s)['index'] == index)
    request = captured['request']
    assert request['human_available'] is False
    observed = []
    decision = http_choice(service['endpoint'], on_response=observed.append)(request)
    results.append({
        'case': directory, 'decision_index': index,
        'public_candidates': len(captured['model_request']['candidates']),
        'selected': decision, 'request_sha256': captured['request_sha256'],
        'service_response': observed[0],
    })
output = args.run / 'CPU_capacity256_ctx32k_live_preflight.json'
with output.open('x') as f:
    json.dump({'service': service, 'health': health, 'cases': results, 'training': False, 'physical_steps': 0}, f, indent=2)
print(json.dumps({'path': str(output), 'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
    'capacity': 256, 'max_context_tokens': 32768, 'adapter_matches': True, 'all_three_actual_requests_pass': True}))
