"""Use the already published prompt-aware exporter; preserve unknown trials."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASE = ROOT/'results/bounded_skills/execution_repairs_20261022/option_ceiling_20261022'
SOURCE = ROOT/'source_native_model_f6987f0d_20261022'


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)


def main():
    exporter = ROOT/'export_original_schema6_measured_final_CPU_20261022.py'
    assert ref(exporter)['sha256'] == '6142d6cdaf2002362724298b329d3619f04ebf7d3499b9d0e5363cceafd499ef'
    accelerator = ROOT/'snapshot_digest_stream_CPU_20261022.py'
    assert ref(accelerator)['sha256'] == '6fb712ba743991e41e3107e33ddacafd13b48db2bb03131b167f4ffd154fc34e'
    old = BASE/'CPU_regression155_closed_r1'
    out = BASE/'CPU_regression155_C2_fixed_r2'
    out.mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONPATH=str(SOURCE), CUDA_VISIBLE_DEVICES='',
        OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    packages = [old/'original90']
    assert json.loads((packages[0]/'manifest.json').read_bytes())['positions'] == 90
    for name in ('measured_packet1', 'measured_packet2'):
        package = out/name
        if not (package/'manifest.json').exists():
            command = [str(ROOT/'.venv/bin/python'), str(exporter), '--source', str(SOURCE),
                '--manifest', str(BASE/f'regression155_f6987f0d/preparation/{name}_manifest.json'),
                '--results', str(old/'raw_view'), '--policy-hashes',
                str(BASE.parent/'qualified90_9716b68c/preparation/registered_pi05_hashes.sha256'),
                '--output', str(package), '--digest-accelerator', str(accelerator),
                '--digest-accelerator-sha256', ref(accelerator)['sha256']]
            subprocess.run(command, env=env, check=True)
        packages.append(package)
    rows, provenance = [], []
    for package in packages:
        manifest = json.loads((package/'manifest.json').read_bytes())
        data = Path(manifest['data']['path'])
        assert ref(data) == manifest['data']
        rows.extend(json.loads(line) for line in data.read_text().splitlines())
        provenance.append(ref(package/'manifest.json'))
    assert len(rows) == len({r['record_id'] for r in rows}) == 155
    assert all(not r['PRO'] and not r['confirmation'] and r['source_split'] == 'train' for r in rows)
    data = out/'positions.jsonl'
    raw = b''.join(json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
        allow_nan=False).encode()+b'\n' for row in rows)
    if data.exists():
        assert data.read_bytes() == raw
    else:
        data.write_bytes(raw)
    manifest = json.loads((packages[0]/'manifest.json').read_bytes())
    manifest.update(positions=155, registered_cases=155, data=ref(data),
        source_packets=provenance, by_category=dict(Counter(r['case']['category'] for r in rows)),
        label_exporter=ref(exporter), canonical_digest_accelerator=ref(accelerator),
        manifest_scope='three disjoint closed packets; fresh same-context self and VLA only')
    manifest.pop('manifest', None)
    write(out/'manifest.json', manifest)
    consumer = Path('/public/home/sunyihan/rd_instruction_20260923/c2_next_a_20261022_0540/gpu_source_r2/consumer')
    validator = BASE/'validate_B2_measured_C2_CPU_20261021.py'
    with (out/'consumer_validation.log').open('x') as stream:
        subprocess.run([str(ROOT/'.venv/bin/python'), str(validator), '--consumer', str(consumer),
            '--schema', str(SOURCE/'rpent/skill_package/schema.json'), '--package', str(out)],
            env=env, check=True, stdout=stream, stderr=subprocess.STDOUT)
    intake = json.loads((out/'C2_intake_validation.json').read_bytes())
    registered = {r['case']: r for r in json.loads((BASE/'regression155_f6987f0d/registration.json').read_bytes())['rows']}
    zero = json.loads((BASE/'zero_control_c7520ae1/CPU_C2_replacements29_r1/record_id_replacements.json').read_bytes())
    aliases = {r['case']: r['replacement_record_id'] for r in zero['rows']}
    mappings = [{'case': row['case']['name'], 'replacement_record_id': row['record_id'],
        'replaces_record_ids': [registered[row['case']['name']]['record_id']]
            + ([aliases[row['case']['name']]] if row['case']['name'] in aliases else []),
        'operation': 'replace context; preserve raw originals; do not append aliases as new states'} for row in rows]
    write(out/'record_id_replacements.json', {'rows': mappings, 'states': 155})
    delivery = {'package': str(out), 'positions': 155, 'raw_attempts': 1165,
        'bound_trials': sum(len(b['trials']) for row in rows for b in row['branches']),
        'unknown_context_trials': sum(len(row['unknown_trials']) for row in rows),
        'consumer_statuses': dict(Counter(r['status'] for r in intake['rows'])),
        'artifacts': {n: ref(out/n) for n in ('positions.jsonl', 'manifest.json',
            'record_id_replacements.json', 'C2_intake_validation.json', 'metrics.json')},
        'PRO': False, 'D2': False, 'confirmation': False, 'training_executed': False}
    assert delivery['bound_trials']+delivery['unknown_context_trials'] == 1165
    write(out/'C2_delivery.json', delivery)
    print(json.dumps(delivery), flush=True)


if __name__ == '__main__':
    main()
