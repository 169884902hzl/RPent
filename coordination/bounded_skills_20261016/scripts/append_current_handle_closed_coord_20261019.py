"""Deliver closed development results without combining immutable sources."""
import fcntl
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root / 'coordination/bounded_skills_20261016'
output = base / 'reports/coord_current_handle_closed_append_20261019.json'
assert not output.exists(), 'Already delivered'
names = ['microwave9611_closed_20261019.json', 'microwave9605_closed_20261019.json',
    'microwave9608_partial_closed_20261019.json', 'box9579_interim_r2_20261019.json',
    'original20_support_interim_r16_20261019.json', 'cup_current_mask_CPU_20261019.json']
inputs = {str(base / 'reports' / name): hashlib.sha256(
    (base / 'reports' / name).read_bytes()).hexdigest() for name in names}
original = json.loads((base / 'reports' / names[4]).read_text())
assert original['completed_physical'] == 122 and len(original['execution_errors']) == 0
assert sum(row['success'] for row in original['cohort']['rows']) == 97
timestamp = datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()
text = f"""

## Codex3 closed current-handle replay and original upper bounds / {timestamp}

1. ede83b18 full microwave replay 9611 is closed 0/2, not a repair pass: close 7 decisions / 331 ticks / 344.984s, planning_unreachable; open 22 / 1501 / 2284.402s, perception. The unchanged-screen current-handle association does disambiguate multiple open-door captures, but does not solve executable contact or terminal identity. CPU 466 passed is kept separate from task success.
2. Prior full f4400223/9605 is closed 0/2: close 33 / 2192 / 3988.124s; open 19 / 1434 / 1825.794s. f75b516d/9608 has only close completed (7 / 331 / 343.660s); open 9608_140 was cancelled while unstarted and replaced, with saved scontrol evidence. Do not count that cancellation as physical failure or call this a complete two-case batch. All raw failures remain.
3. Real cream-cheese-box 4db4ea4/9579 is complete 20/20, Wilson95 [0.8388748419471806, 1.0], median 3 decisions / 433 ticks / 334.725s, zero pi0.5 calls. This is original-task development feasibility, not confirmation or a category qualification. The ec89f74 historic box_transfer cases are cans and remain separately named.
4. Fixed ec89f74 originals at 00:42 PDT: 97 native successes / 122 complete / 220 registered, 98 incomplete, zero execution_error. Per category successes/complete: bowl 16/16, can 12/14, container 14/14, cup 7/14, drawer close 14/15, drawer open 12/15, microwave close 0/1, open 0/1, plate 0/2, stove off 11/15, on 11/15. Wilson intervals and per-episode timing/skills are in original20_support_interim_r16_20261019.json. Partial completed states are not a balanced full cohort.
5. C3 continues the existing monitored queue and public-geometry failure diagnosis; C1 audits source/case/denominator; C2 uses exact-context prefix labels only. Two saved cup overlays were actually inspected: correct white-yellow mug mask, only main-camera measurement, no wrist match; opposed-flank support is missing, not established physical unreachability. Full report: {base}/progress_current_handle_identity_20261019.md. No training, PRO, confirmation regrading or hardware; permanent confirmation exclusion remains. Only node02/nice500, protected jobs and held jobs untouched.

Evidence SHA256 (report paths):
{json.dumps(inputs, indent=2)}
"""
raw = text.encode()
path = Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md')
with path.open('ab') as stream:
    fcntl.flock(stream, fcntl.LOCK_EX)
    stream.seek(0, 2)
    start = stream.tell()
    stream.write(raw)
    stream.flush()
    end = stream.tell()
receipt = {'path': str(path), 'append_start': start, 'append_end': end,
    'appended_bytes': len(raw), 'appended_sha256': hashlib.sha256(raw).hexdigest(),
    'inputs': inputs, 'source_commit': 'ede83b18', 'training': False}
with output.open('x') as stream:
    json.dump(receipt, stream, indent=2)
    stream.write('\n')
print(json.dumps(receipt))
