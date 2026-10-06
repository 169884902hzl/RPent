"""CPU-only explicit 4103 queue preparation; never open PRO task contents."""
import argparse
import hashlib
import json
from pathlib import Path


def identity(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def load_pinned(record):
    path = Path(record['path'])
    if identity(path)['sha256'] != record['sha256']:
        raise ValueError(f'pinned file changed: {path}')
    return json.loads(path.read_text())


parser = argparse.ArgumentParser()
parser.add_argument('--plan', type=Path, required=True)
args = parser.parse_args()
plan = json.loads(args.plan.read_text())
root, prep, source = (Path(plan[key]) for key in ('root', 'preparation', 'source_snapshot'))
parent = load_pinned(plan['parent_index'])
assert (parent['total'], parent['original'], parent['development']) == (20, 10, 10)
prep.mkdir(parents=True, exist_ok=True)
files, episodes, diffs, asset_evidence = [], [], [], []
for registered in parent['files']:
    old = load_pinned(registered)
    assert old['baseline'] == plan['baseline']
    assert old['model_revision'] == plan['model_revision']
    assert old['evaluation_only'] is True and old['training_allowed'] is False
    original_budget = dict(old['budget'])
    budget = {**original_budget, **plan['budget_overrides']}
    assert tuple(budget[key] for key in ('max_decisions', 'max_chunks', 'max_episode_steps', 'prompt_limit')) == (100, 80, 10000, 3072)
    assert 'observation_pose_v1' not in budget
    diff = {key: {'before': original_budget.get(key, 'unset'), 'after': value}
            for key, value in budget.items() if original_budget.get(key, 'unset') != value}
    new = {**old, 'budget': budget, 'purpose': '20-episode current-default runtime550 development smoke; not qualification or clean single-factor comparison',
           'parent_job': 4103, 'parent_plan': registered,
           'configuration_diff': diff, 'qualification_authorized': False}
    path = prep / f"{registered['cohort']}_part{registered['part']}.json"
    path.write_text(json.dumps(new, indent=2) + '\n')
    files.append({**identity(path), 'cohort': registered['cohort'], 'part': registered['part'], 'episodes': len(old['episodes'])})
    episodes.extend((registered['cohort'], item['suite'], item['task'], item['seed']) for item in old['episodes'])
    diffs.append({'cohort': registered['cohort'], 'part': registered['part'], 'diff': diff})
    # This is prior CPU validation evidence, not a new asset/content audit.
    # Only the registered task identities and opaque stored hashes are read.
    old_assets = root / f"results/harness_v5/runtime536_smoke20_20261006/job4103/part{registered['part']}/assets_{registered['cohort']}.json"
    entries = json.loads(old_assets.read_text())
    assert [item['episode'] for item in entries] == old['episodes']
    for item in entries:
        assert item['trials'] > item['episode']['seed']
        for key in ('bddl', 'init'):
            asset = Path(item[key]['path'])
            asset.resolve(strict=True)
            item[key]['current_exists'] = True
            item[key]['current_bytes'] = asset.stat().st_size
            # No PRO BDDL/init payload is opened or parsed here.
    asset_evidence.append({'cohort': registered['cohort'], 'part': registered['part'],
                           'prior_preflight': identity(old_assets), 'records': entries})
assert len(episodes) == len(set(episodes)) == 20
assert sum(item[0] == 'original' for item in episodes) == sum(item[0] == 'development' for item in episodes) == 10
index = {**parent, 'files': files, 'source_snapshot': str(source),
         'parent_index': plan['parent_index'], 'parent_job': 4103,
         'purpose': 'Explicit current-default runtime550 smoke; source and quality remain unfrozen',
         'configuration_plan': identity(args.plan), 'qualification_authorized': False}
index_path = prep / 'manifest.json'
index_path.write_text(json.dumps(index, indent=2) + '\n')
rd = root.parent / 'rd_instruction_20260923'
paths = [root / '.venv/bin/python', root / 'runtime_config/config.yaml',
         root / 'assets/sam3/sam3.pt', root / 'assets/pi05',
         root.parent / 'liberopro_hf/c86fc3b8293185a6f373677018ff3e37f8391602',
         rd / 'v5r_20261001/qualified_service_sources_bf097673/v5r_server.py',
         rd / 'v5_models/qwen3_5_4b_851bf6e8/config.json',
         rd / 'v5r_20261001/package3072', Path(plan['checkpoint']),
         rd / 'v31_package_decider_2048_socket_20260925a/parallel_schema.py',
         rd / 'v31_package_decider_2048_socket_20260925a/tokenizer_config.json']
resources = [{'path': str(path.resolve(strict=True)), 'bytes': path.stat().st_size,
              'is_directory': path.is_dir()} for path in paths]
source_files = []
service_dependencies = []
if source.exists():
    source_files = [identity(source / name) for name in ('harness_v5_eval.py', 'v5_batch_eval.py',
        'robots/libero/v5_runtime.py', 'robots/libero/v5_state.py', 'robots/libero/v5_recovery.py',
        'robots/libero/v5_action_effect.py', 'robots/libero/v5_subtasks.py',
        'scripts/run_v5_runtime536_smoke20.sbatch')]
    launcher = (source / 'scripts/run_v5_runtime536_smoke20.sbatch').read_text()
    pp = next(line.split('=', 1)[1] for line in launcher.splitlines() if line.startswith('PP='))
    service_dependencies = [{'path': str(Path(path).resolve(strict=True)), 'is_directory': Path(path).is_dir()}
                            for path in pp.split(':')]
report = {'preparation_passed': True, 'source_snapshot_ready': source.exists(),
          'scope': 'CPU inputs/resources preparation only. No PRO task or initial-state payload opened; prior asset check evidence reused. '
                   'No GPU/model/SAM/physics, no qualification. Root launcher runs its full preflight before GPU loading.',
          'plan': identity(args.plan), 'producer': identity(__file__), 'manifest': identity(index_path),
          'episode_identities_equal_4103': True, 'episodes': episodes, 'configuration_diff': diffs,
          'source_files': source_files, 'resources': resources,
          'service_pythonpath_dependencies': service_dependencies, 'prior_asset_evidence': asset_evidence,
          'checkpoint_identity': {'path': plan['checkpoint'], 'registered_sha256': plan['model_revision'],
                                  'check': 'CPU checks existence only; launcher health must verify registered revision and 3072 context'},
          'external_endpoints_needed': [],
          'local_endpoints': {'decision': 'launcher starts registered v5r System One service on dynamically selected localhost port',
                              'sam3_pi05': 'v5_batch_eval starts shared local component services on dynamically selected localhost ports'}}
destination = prep / 'cpu_preparation_report.json'
destination.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'manifest': identity(index_path), 'report': identity(destination),
                  'episodes': len(episodes), 'preparation_passed': True, 'source_snapshot_ready': source.exists(),
                  'first_configuration_diff': diffs[0]['diff']}))
