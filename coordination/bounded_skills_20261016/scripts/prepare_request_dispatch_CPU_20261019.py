"""Prepare unchanged original states for serial versus production worker checks."""
import copy
import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASE = ROOT / 'coordination/bounded_skills_20261016'
SOURCE = ROOT / 'source_bounded_request_dispatch_20261019_1378906e'
ARCHIVE_SHA = 'ac8cfd37c222624c054e1e3f4e892c23e4928354f28f2ba0288c4100dbd8dfe0'


def main():
    archive = ROOT / 'bounded_request_dispatch_20261019_1378906e.tar.gz'
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == ARCHIVE_SHA
    tests_path = BASE / 'reports/cpu_request_dispatch_tests_20261019.json'
    tests = json.loads(tests_path.read_bytes())
    assert tests['exit_code'] == 0
    for name, sha in tests['files'].items():
        assert hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() == sha
    pair_path = BASE / 'reports/request_dispatch_pair_CPU_20261019.json'
    pair = json.loads(pair_path.read_bytes())
    assert pair['source_snapshot'] == str(SOURCE)
    assert len(pair['records']) == 5 and all(r['candidate_and_diagnostic_bytes_equal'] for r in pair['records'])
    old = json.loads((BASE / 'reports/chunk_v3_spawn_w1_20261019_preparation.json').read_bytes())
    previous = Path(old['manifest']['path'])
    assert hashlib.sha256(previous.read_bytes()).hexdigest() == old['manifest']['sha256']
    original = json.loads(previous.read_bytes())
    original_config_path = Path(original['base_config']['path'])
    assert original_config_path.is_absolute() and original_config_path.is_file()
    assert hashlib.sha256(original_config_path.read_bytes()).hexdigest() == original['base_config']['sha256']
    original_config = json.loads(original_config_path.read_bytes())
    preparation = ROOT / 'results/bounded_skills/feasibility_20261017/preparation'
    for workers in (1, 4):
        tag = f'chunk_v3_request_w{workers}_20261019'
        plan = copy.deepcopy(original)
        plan['source_commit'] = tests['source_commit']
        plan['source_snapshot'] = {'path': str(SOURCE), 'code_archive_sha256': ARCHIVE_SHA}
        config = copy.deepcopy(original_config)
        config.get('budget', config).update(prefix_consequence_workers=workers,
                                           request_consequence_workers=workers)
        config_path = preparation / f'{tag}_config.json'
        with config_path.open('x') as stream:
            json.dump(config, stream, indent=2)
            stream.write('\n')
        plan['base_config'] = {'path': str(config_path),
                               'sha256': hashlib.sha256(config_path.read_bytes()).hexdigest()}
        assert plan['cases'] == original['cases']
        manifest = preparation / f'original20_manifest_{tag}.json'
        with manifest.open('x') as stream:
            json.dump(plan, stream, indent=2)
            stream.write('\n')
        launcher = SOURCE / 'scripts/run_bounded_21f0744_20261017.sbatch'
        assert SOURCE.is_absolute() and SOURCE.is_dir()
        assert all(path.is_absolute() and path.is_file() for path in (config_path, manifest, launcher))
        environment = dict(os.environ, PYTHONPATH=str(SOURCE), LIBERO_TYPE='standard',
                           LIBERO_CONFIG_PATH=str(ROOT / 'runtime_config'), CUDA_VISIBLE_DEVICES='',
                           OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
        command = [str(ROOT / '.venv/bin/python'), '-m', 'scripts.v5_probe_preflight',
                   '--manifest', str(manifest), '--states']
        result = subprocess.run(command, cwd=SOURCE, env=environment, text=True, capture_output=True)
        log = preparation / f'preflight_{tag}.log'
        log.write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f'preflight failed: {log}')
        report = {'source_commit': tests['source_commit'], 'snapshot': str(SOURCE),
                  'archive_sha256': ARCHIVE_SHA, 'n_states': len(plan['cases']),
                  'prefix_consequence_workers': workers, 'request_consequence_workers': workers,
                  'same_original_cases': plan['cases'] == original['cases'],
                  'base_config': plan['base_config'],
                  'schema_sha256': hashlib.sha256((SOURCE / 'rpent/skill_package/schema.json').read_bytes()).hexdigest(),
                  'manifest': {'path': str(manifest), 'sha256': hashlib.sha256(manifest.read_bytes()).hexdigest()},
                  'preflight': {'command': command, 'exit_code': result.returncode, 'log': str(log)},
                  'cpu_tests': {'path': str(tests_path), 'sha256': hashlib.sha256(tests_path.read_bytes()).hexdigest()},
                  'saved_cpu_pair': {'path': str(pair_path), 'sha256': hashlib.sha256(pair_path.read_bytes()).hexdigest()},
                  'physical_validation': 'pending same-source same-launcher startup',
                  'training': False, 'confirmation': False, 'pi05_in_oracle': False}
        with (BASE / f'reports/{tag}_preparation.json').open('x') as stream:
            json.dump(report, stream, indent=2)
            stream.write('\n')
        print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
