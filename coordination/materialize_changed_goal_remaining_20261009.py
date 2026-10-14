"""Prepare registered changed-goal geometry on CPU without policy execution."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
OUTPUT = ROOT / 'results/harness_v5/perturb_changed_goal_geometry_20261009_r1'
ADAPTER = ROOT / 'coordination/perturb_changed_goal_adapter_20261009_r1'
SOURCE = ROOT / 'source_v5_native_stop_guard_20261009_r2'
GENERATOR = ROOT / 'coordination/prepare_changed_goal_skill_pools_20261009_r2.py'
REGISTRY = ROOT / 'results/harness_v5/perturb_changed_goal_registry_20261009_r1'
MOKA = ROOT / 'results/harness_v5/perturb_changed_goal_moka_registry_20261009_r2'
CELLS = [('vla_subtask', c) for c in ('bottle', 'box', 'cup', 'frypan', 'moka pot')]
CELLS += [('place', 'on'), ('place', 'in')]


def main():
    env = {**os.environ, 'LIBERO_TYPE': 'standard', 'LIBERO_CONFIG_PATH': str(ROOT / 'runtime_config'),
           'PYTHONPATH': f'{ADAPTER}:{SOURCE}:{SOURCE / "scripts"}',
           'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}

    def prepare(cell):
        skill, category = cell
        name = f'{skill}_{category.replace(" ", "_")}'
        output = OUTPUT / f'selection_{name}'
        registry = MOKA if category == 'moka pot' else REGISTRY
        log = ROOT / 'coordination' / f'changed_goal_{name}_materialization_20261009.log'
        command = [str(ROOT / '.venv/bin/python'), str(GENERATOR), '--pool', str(registry / 'selection.json'),
                   '--skill', skill, '--category', category, '--output', str(output)]
        with log.open('x') as stream:
            result = subprocess.run(command, env=env, stdout=stream, stderr=subprocess.STDOUT)
        print(json.dumps({'cell': name, 'exit_code': result.returncode, 'log': str(log)}), flush=True)
        return result.returncode

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(prepare, CELLS))
    if any(results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
