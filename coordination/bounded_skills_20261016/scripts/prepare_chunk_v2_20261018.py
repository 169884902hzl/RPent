"""Pin the v2 source/unchanged original states and run the shared CPU preflight."""
import argparse
import hashlib
import json
import os
import subprocess
import tarfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--commit', default='77ee4ff')
parser.add_argument('--tag', default='chunk_v2_20261018')
parser.add_argument('--archive-sha256', default='530486fe43e1fdf546716dc72c05daf1f8b32341b48ba53f06187c9d92000f78')
parser.add_argument('--cpu-validation-receipt', type=Path)
args = parser.parse_args()
root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
commit = args.commit
archive = root/f'bounded_{args.tag}_{commit}.tar.gz'
# Retain the original archive naming for its existing preparation receipt.
if args.tag == 'chunk_v2_20261018' and commit == '77ee4ff':
    archive = root/'bounded_chunk_v2_77ee4ff_20261018.tar.gz'
archive_sha = args.archive_sha256
assert hashlib.sha256(archive.read_bytes()).hexdigest() == archive_sha
source = root/f'source_bounded_{args.tag}_{commit}'
source.mkdir()
with tarfile.open(archive) as stream:
    stream.extractall(source)
preparation = root/'results/bounded_skills/feasibility_20261017/preparation'
previous = preparation/'original20_manifest_precontact_20261018.json'
plan = json.loads(previous.read_text())
plan.update(source_commit=commit, source_snapshot={'path':str(source), 'code_archive_sha256':archive_sha})
# No case, BDDL, state identity, split, predicate, budget or robot limit changes.
manifest = preparation/f'original20_manifest_{args.tag}.json'
manifest.write_text(json.dumps(plan, indent=2)+'\n')
assert plan['cases'] == json.loads(previous.read_text())['cases']
environment = os.environ.copy()
environment.update(PYTHONPATH=str(source), LIBERO_TYPE='standard', LIBERO_CONFIG_PATH=str(root/'runtime_config'),
                   CUDA_VISIBLE_DEVICES='', OPENBLAS_NUM_THREADS='1')
check = subprocess.run([str(root/'.venv/bin/python'), '-m', 'scripts.v5_probe_preflight',
    '--manifest', str(manifest), '--states'], cwd=source, env=environment, text=True, capture_output=True)
log = preparation/f'preflight_{args.tag}.log'
log.write_text(check.stdout+check.stderr)
assert check.returncode == 0, check.stderr
report = {'source_commit':commit, 'snapshot':str(source), 'archive_sha256':archive_sha,
    'schema_version':'bounded-skills/2', 'schema_sha256':hashlib.sha256((source/'rpent/skill_package/schema.json').read_bytes()).hexdigest(),
    'manifest':{'path':str(manifest),'sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()},
    'preflight':{'exit_code':check.returncode,'log':str(log)}, 'n_states':len(plan['cases']),
    'entry':'scripts.probe_bounded_feasibility:episode', 'interpreter':str(root/'.venv/bin/python'),
    'cpu_validation': ({'receipt':str(args.cpu_validation_receipt),
        'sha256':hashlib.sha256(args.cpu_validation_receipt.read_bytes()).hexdigest(),
        'results':json.loads(args.cpu_validation_receipt.read_text())}
        if args.cpu_validation_receipt else None),
    'physical_validation':'pending same-launcher startup', 'training':False,'confirmation':False,'pi05_in_oracle':False}
(base/'reports'/f'{args.tag}_preparation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
