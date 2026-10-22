"""Register fixed D2 and original holdout evaluations with the live model."""
import argparse
import copy
import hashlib
import json
from pathlib import Path


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    root = Path('/public/home/sunyihan/rpent_libero_eval')
    base = root/'results/bounded_skills/execution_repairs_20261022'
    revision = json.loads((args.source/'SOURCE_REVISION.json').read_bytes())['commit']
    out = base/('option_ceiling_20261022/native_model_'+revision[:8]+'/preparation')
    ready_path = Path('/public/home/sunyihan/rd_instruction_20260923/c2_next_a_20261022_0540/service_job11484/service_ready.json')
    ready = json.loads(ready_path.read_bytes())
    old = root/'results/bounded_skills/schema6_20261020/model_view_2df3a44e/preparation'
    model = json.loads((old/'manifest.json').read_bytes())
    model.update(source=str(args.source), source_commit=revision)
    model['model_service'] = {'endpoint': ready['endpoint'],
        'health_url': ready['endpoint'].replace('/v1/bounded-choice', '/health'),
        'adapter_sha256': ready['adapter_sha256'],
        'schema_sha256': ready['source']['schema_sha256'],
        'contract_sha256': ready['source']['contract_sha256'], 'ready_receipt': ref(ready_path)}
    model['jobs'].insert(0, json.loads((old/'bowl_K1_changed_view.json').read_bytes())['jobs'][0])
    assert len(model['jobs']) == 6
    model['parent_registration'] = ref(old/'manifest.json')
    model['holdout_scope'] = 'the original six episode/K arms: three init identities at K1 and K4'
    write(out/'model_original6.json', model)
    write(out/'model_startup.json', dict(model, jobs=model['jobs'][:1]))
    parent = base/'D2_option_fallback_a3c7cf43/preparation/D2_recovery1.json'
    d2 = json.loads(parent.read_bytes())
    assert len(d2['jobs']) == 40
    oracle = copy.deepcopy(d2)
    oracle.update(source=str(args.source), source_commit=revision,
        parent_registration=ref(parent), runtime_change='default whole instruction budget; observe accounting; native endpoint path preservation')
    write(out/'oracle_D2_recovery1.json', oracle)
    model_d2 = copy.deepcopy(model)
    model_d2['runtime_budget'] = {'sim_steps': 10000, 'decisions': 160, 'recovery_budget': 1}
    model_d2['recovery_scope'] = 'reset by public hold transitions or successful call_vla, not private oracle subtask labels'
    model_d2['parent_registration'] = ref(parent)
    model_d2['jobs'] = [{'kind': 'model', 'case': row['case'], 'k': 4,
        'split': 'd2_evaluation'} for row in d2['jobs']]
    write(out/'model_D2_recovery1.json', model_d2)
    smoke = json.loads((base/'option_ceiling_20261022/fulltask124c5654/preparation/smoke10.json').read_bytes())
    smoke.update(source=str(args.source), source_commit=revision)
    write(out/'smoke10.json', smoke)
    write(out/'vla_startup.json', dict(oracle, jobs=oracle['jobs'][:1]))
    print(json.dumps({'output': str(out), 'source': revision,
        'D2_oracle': 40, 'D2_model': 40, 'original_model_arms': 6,
        'original_initial_identities': 3, 'adapter_sha256': ready['adapter_sha256']}))


if __name__ == '__main__':
    main()
