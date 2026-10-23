"""Resume only unfinished cases after real 32k HTTP request verification."""
import hashlib
import json
from pathlib import Path
import subprocess

root = Path('/public/home/sunyihan/rpent_libero_eval')
run = root/'results/bounded_skills/next_b_pi_first_20261023'
prep = run/'preparation'

def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

preflight = run/'CPU_capacity256_ctx32k_live_preflight.json'
data = json.loads(preflight.read_text())
assert len(data['cases']) == 3
assert data['health']['max_context_tokens'] == 32768
assert data['health']['single_code_capacity'] == 256
script = (prep/'eval_worker0.sbatch').read_text()
for shard in (0, 1):
    old = prep/f'model_d2_{shard}_capacity256.json'
    new = prep/f'model_d2_{shard}_capacity256_ctx32k.json'
    plan = json.loads(old.read_text())
    plan['model_service']['endpoint'] = 'http://node02:18076/v1/bounded-choice'
    plan['model_service']['health_url'] = 'http://node02:18076/healthz'
    plan['model_service']['capacity256_ctx32k_preflight'] = ref(preflight)
    plan['model_service']['owned_ctx32k_registration'] = ref(prep/'capacity256_ctx32k_service_submission.json')
    plan['transport_ctx32k_parent_manifest'] = ref(old)
    with new.open('x') as f:
        json.dump(plan, f, indent=2)
    script = script.replace(str(old), str(new))
script = script.replace('rd-c3-s6-v7-eval-worker-0', 'rd-c3-s6-v7-eval-resume32k')
path = prep/'eval_worker0_ctx32k.sbatch'
with path.open('x') as f:
    f.write(script)
job = subprocess.check_output(['sbatch', '--parsable', str(path)], text=True).strip()
registration = {'job': job, 'script': ref(path), 'preflight': ref(preflight),
    'resume_case_pointers_unchanged': True, 'completed_cases_rerun': False,
    'failed_attempts_preserved': True, 'execution_source_unchanged': True,
    'shared_C2_service_modified': False}
with (prep/'eval_worker0_ctx32k_submission.json').open('x') as f:
    json.dump(registration, f, indent=2)
print(json.dumps(registration))
