# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Resolve the two intended plate identities across differently ordered manifests."""
import hashlib
import json
import os
import signal
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
tag = 'chunk_v3_inclined_rim_plate_20261018'
output = base/'reports/plate_case_identity_correction_20261018.json'
assert not output.exists(), 'Preserve the existing correction receipt'
old = json.loads((base/'reports/original20_support_roundrobin_20261018_full_submission.json').read_text())
prep = json.loads((base/'reports/chunk_v3_inclined_rim_20261018_preparation.json').read_text())
before = json.loads(Path(old['manifest']['path']).read_text())
raw = Path(prep['manifest']['path']).read_bytes()
assert hashlib.sha256(raw).hexdigest() == prep['manifest']['sha256']
after = json.loads(raw)
targets = [before['cases'][index] for index in (8, 19)]
indices = []
for case in targets:
    matches = [index for index, other in enumerate(after['cases']) if other == case]
    assert len(matches) == 1, (case, matches)
    indices.append(matches[0])
names = ','.join(case['name'] for case in targets)
prep['selection_reference'] = {'receipt': str(base/'reports/original20_support_roundrobin_20261018_full_submission.json'),
    'old_indices': [8, 19], 'new_indices': indices, 'cases': targets}
(base/'reports'/f'{tag}_preparation.json').write_text(json.dumps(prep, indent=2)+'\n')
command = [str(root/'.venv/bin/python'), str(base/'scripts/submit_chunk_v2_20261018.py'),
    '--tag', tag, '--oracle-only', '--expected-case-names', names]
negative = subprocess.run(command+['--indices', '8,19', '--startup-index', '8'],
    text=True, capture_output=True)
assert negative.returncode != 0 and 'Case identity mismatch' in negative.stderr
assert not (base/'reports'/f'{tag}_startup_submission.json').exists()
# This replaces only our queue controller; running simulation jobs keep going.
pid = 1825717
proc_command = Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\x00', b' ').decode()
assert 'monitor_v3_timing_20261018.py' in proc_command and '--tag chunk_v3_inclined_rim_20261018 ' in proc_command
os.kill(pid, signal.SIGTERM)
completed = subprocess.run(command+['--indices', ','.join(map(str, indices)),
    '--startup-index', str(indices[0])], text=True, capture_output=True, check=True)
report = {'time_pacific': datetime.now(ZoneInfo('America/Los_Angeles')).isoformat(),
    'reason': 'Round-robin indices 8/19 were incorrectly reused in a category-ordered manifest.',
    'incorrect_full_job': '9498',
    'incorrect_selected_cases': [after['cases'][index] for index in (8, 19)],
    'correct_indices': indices, 'correct_cases': targets,
    'source_commit': prep['source_commit'], 'manifest': prep['manifest'],
    'negative_test': {'exit_code': negative.returncode, 'stderr': negative.stderr,
        'submitted_job': False}, 'stopped_controller': {'pid': pid, 'command': proc_command},
    'startup_submission': json.loads(completed.stdout),
    'running_or_held_jobs_modified': False, 'training': False,
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report))
