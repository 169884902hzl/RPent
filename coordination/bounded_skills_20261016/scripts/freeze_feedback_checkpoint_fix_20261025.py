"""Freeze callback-free checkpoints on the registered execution snapshot."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile

repo = Path('/home/agilex/cobot_magic/rpent_libero_eval')
base = Path('/tmp/rd_task_ladder_blacklist_r3_20261025')
source = Path('/tmp/rd_task_ladder_feedback_checkpoint_r3_20261025')
base_tree = '44faeea5c7e026d816490d7104e7a33440b777a5'
names = (
    'rpent/skill_package/feedback.py',
    'robots/libero/bounded_hybrid_diagnostic.py',
    'robots/libero/bounded_offline_labels.py',
    'robots/libero/bounded_success_loop.py',
    'scripts/probe_bounded_hybrid_d2.py',
    'tests/unit_tests/robots/libero/test_bounded_feedback_checkpoint.py',
    'tests/unit_tests/robots/libero/test_bounded_offline_labels.py',
    'tests/unit_tests/robots/libero/test_bounded_hybrid_diagnostic.py',
)
assert not source.exists()
shutil.copytree(base, source, copy_function=os.link, symlinks=True)
for name in names:
    target = source / name
    target.unlink(missing_ok=True)
    shutil.copy2(repo / name, target)
with tempfile.TemporaryDirectory() as tmp:
    env = {**os.environ, 'GIT_INDEX_FILE': str(Path(tmp) / 'index')}
    subprocess.run(['git', 'read-tree', base_tree], cwd=repo, env=env, check=True)
    for name in names:
        blob = subprocess.check_output(['git', 'hash-object', '-w', str(source / name)],
            cwd=repo, text=True).strip()
        subprocess.run(['git', 'update-index', '--add', '--cacheinfo',
            f'100644,{blob},{name}'], cwd=repo, env=env, check=True)
    tree = subprocess.check_output(['git', 'write-tree'], cwd=repo, env=env, text=True).strip()
archive = Path('/tmp') / f'feedback_checkpoint_fix_{tree[:8]}.tgz'
with tarfile.open(archive, 'w:gz') as out:
    for name in names:
        out.add(source / name, arcname=name)
reg = {
    'base_tree': base_tree, 'tree': tree, 'source': str(source),
    'archive': str(archive), 'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
    'files': {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in names},
    'scope': 'checkpoint feedback switches/read count; restore current-host callbacks; '
        'CPU annotation retains captured public feedback and aggressive policy',
    'contract_changed': False, 'control_code_changed': False,
    'program_error_cohort_preserved': 'panels5_blacklist_r2',
}
Path('/tmp/feedback_checkpoint_fix_registration.json').write_text(json.dumps(reg, indent=2) + '\n')
print(json.dumps(reg, indent=2))
