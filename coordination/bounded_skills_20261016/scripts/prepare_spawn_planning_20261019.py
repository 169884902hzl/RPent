"""Pin both serial/spawn configs to the same original cases and source."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root / 'coordination/bounded_skills_20261016'
commit = '7ffe2118dca7a74c7455b89a1ef85c9b48dcd64e'
archive_sha = 'bcf8d24823c63e72335ee2c661b9c7799669b7effc27c3c0019807c89f28ed97'
source = root / 'source_bounded_spawn_planning_20261019_7ffe2118'
prior = json.loads((base / 'reports/chunk_v3_joint_guides_20261019_preparation.json').read_text())
previous_plan = json.loads(Path(prior['manifest']['path']).read_bytes())
initial = json.loads(Path(previous_plan['base_config']['path']).read_bytes())
evidence = json.loads((base / 'reports/runtime_spawn_oracle_CPU_20261019.json').read_text())
assert all(row['complete_context_labels_and_choice_equal'] for row in evidence['records'])
for workers in (1, 4):
    tag = f'chunk_v3_spawn_w{workers}_20261019'
    config = json.loads(json.dumps(initial))
    config.get('budget', config)['prefix_consequence_workers'] = workers
    preparation = Path(prior['manifest']['path']).parent
    config_path = preparation / f'{tag}_config.json'
    config_path.write_text(json.dumps(config, indent=2)+'\n')
    plan = json.loads(json.dumps(previous_plan))
    plan.update(source_commit=commit, source_snapshot={'path': str(source), 'code_archive_sha256': archive_sha},
                base_config={'path': str(config_path), 'sha256': hashlib.sha256(config_path.read_bytes()).hexdigest()})
    manifest = preparation / f'original20_manifest_{tag}.json'
    assert not manifest.exists(), 'preserve prepared source/config identity'
    manifest.write_text(json.dumps(plan, indent=2)+'\n')
    for path in (config_path, manifest, source / 'scripts/run_bounded_21f0744_20261017.sbatch'):
        assert path.is_absolute() and path.is_file()
    command = [str(root / '.venv/bin/python'), '-m', 'scripts.v5_probe_preflight',
               '--manifest', str(manifest), '--states']
    checked = subprocess.run(command, cwd=source, capture_output=True, text=True,
        env={**os.environ, 'PYTHONPATH': str(source), 'LIBERO_TYPE': 'standard',
             'LIBERO_CONFIG_PATH': str(root / 'runtime_config'), 'CUDA_VISIBLE_DEVICES': '',
             'OPENBLAS_NUM_THREADS': '1'})
    log = preparation / f'{tag}_preflight.log'
    log.write_text(checked.stdout+checked.stderr)
    checked.check_returncode()
    receipt = {'source_commit': commit, 'snapshot': str(source), 'archive_sha256': archive_sha,
               'manifest': {'path': str(manifest), 'sha256': hashlib.sha256(manifest.read_bytes()).hexdigest()},
               'prefix_consequence_workers': workers, 'n_states': len(plan['cases']),
               'same_original_cases': plan['cases'] == previous_plan['cases'],
               'preflight': {'exit_code': checked.returncode, 'log': str(log), 'command': command},
               'entry': 'scripts.probe_bounded_feasibility:episode',
               'interpreter': str(root / '.venv/bin/python'),
               'physical_validation': 'not yet submitted; same-launcher startup still required',
               'training': False, 'confirmation': False}
    (base / 'reports' / f'{tag}_preparation.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt), flush=True)
