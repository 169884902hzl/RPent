"""Deploy the tested joint-guide source and CPU-check its original state IDs."""
import hashlib
import json
import os
import subprocess
import tarfile
from pathlib import Path

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root / 'coordination/bounded_skills_20261016'
tag = 'chunk_v3_joint_guides_20261019'
commit = '6958aefe1ef60c8b9f92e029f308762fdadb81f7'
archive = root / 'bounded_chunk_v3_joint_guides_20261019_6958aefe.tar.gz'
expected = '871aca20ae186821543721917c091795273cea3b8b3fabd9e234ec1b1a43ff7c'
if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
    raise ValueError('source archive differs from the tested commit')
source = root / 'source_bounded_chunk_v3_joint_guides_20261019_6958aefe'
if not source.exists():
    source.mkdir()
    with tarfile.open(archive) as stream:
        stream.extractall(source)
prior = json.loads((base / 'reports/chunk_v3_band_seeds_20261019_preparation.json').read_bytes())
manifest_directory = root / 'results/bounded_skills/feasibility_20261017/preparation'
manifest = manifest_directory / f'original20_manifest_{tag}.json'
plan = json.loads(Path(prior['manifest']['path']).read_bytes())
plan['source_commit'] = commit
plan['source_snapshot'] = {'path': str(source), 'code_archive_sha256': expected}
if manifest.exists():
    if json.loads(manifest.read_bytes()) != plan:
        raise ValueError('preparation cannot overwrite a different plan')
else:
    manifest.write_text(json.dumps(plan, indent=2)+'\n')
for path in (source / 'scripts/run_bounded_21f0744_20261017.sbatch',
             Path(plan['base_config']['path']), manifest):
    if not path.is_absolute() or not path.is_file():
        raise ValueError(f'launcher path must exist and be absolute: {path}')
command = [str(root / '.venv/bin/python'), '-m', 'scripts.v5_probe_preflight',
           '--manifest', str(manifest), '--states']
checked = subprocess.run(command, cwd=source, capture_output=True, text=True,
    env={**os.environ, 'PYTHONPATH': str(source), 'LIBERO_TYPE': 'standard',
         'LIBERO_CONFIG_PATH': str(root / 'runtime_config'), 'CUDA_VISIBLE_DEVICES': '',
         'OPENBLAS_NUM_THREADS': '1'})
log = manifest_directory / f'preflight_{tag}.log'
log.write_text(checked.stdout+checked.stderr)
checked.check_returncode()
report = {'source_commit': commit, 'snapshot': str(source), 'archive_sha256': expected,
    'manifest': {'path': str(manifest), 'sha256': hashlib.sha256(manifest.read_bytes()).hexdigest()},
    'schema_version': 'bounded-skills/3',
    'schema_sha256': hashlib.sha256((source / 'rpent/skill_package/schema.json').read_bytes()).hexdigest(),
    'preflight': {'exit_code': checked.returncode, 'log': str(log)}, 'n_states': len(plan['cases']),
    'entry': 'scripts.probe_bounded_feasibility:episode',
    'interpreter': str(root / '.venv/bin/python'), 'training': False, 'confirmation': False,
    'pi05_in_oracle': False, 'physical_validation': 'pending same-launcher startup',
    'cpu_checks': '291 passed / 226.48s; prior surface-focused15 and guide3 overlap'}
out = base / 'reports' / f'{tag}_preparation.json'
out.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report))
