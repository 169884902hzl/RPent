# Copyright 2026 The RPent Authors.
# SPDX-License-Identifier: Apache-2.0
"""Publish source identity and private branch evidence contract, without full log reads."""
import fcntl
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root / 'coordination/bounded_skills_20261016'
receipt = json.loads((base / 'reports/hybrid_d2_e9aeaf9b_startup_submission_20261019.json').read_text())
message = f"""

[Codex3 | {datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()} | D2_HYBRID_SOURCE_AND_PRIVATE_INTERFACE]
1. New 10/19 user direction implemented at e9aeaf9b (pushed harness-v5), eval only. Snapshot {receipt['snapshot']}; archive SHA256 {receipt['archive_sha256']}; manifest {receipt['manifest']['path']} SHA256 {receipt['manifest']['sha256']}. Entry scripts.probe_bounded_hybrid_d2:main; interpreter {root}/.venv/bin/python. CPU31 pass/18.03s; additional unavailable-VLA regression6 pass/0.24s (overlapping counts). CPU D2 init hash validation40/40, existing predicate split has zero uncovered clauses: pick44,on22,in22,open2,close2,turn_on2. This is rule-shape coverage, not measured progress coverage or success.
2. Source scope is exactly D2 eight PRO development suites/task0-4/init40. No PRO test targets, training, confirmation states or history ingestion. Normal original-only oracle service remains restricted. Public schema3 and legality2 unchanged; private original judge13 unchanged. D2-only private facade reuses its existing rules; no new PRO-specific oracle progress recipes. 92/99 are targets, never admission gates.
3. C2 evidence contract: every subtask has private_branchpoint.pkl integrity/physics hash, exact initial request SHA and empty prefix identity, hash-pinned offline annotation context; one self branch and three independently seeded pi0.5 branches; each summary includes selected first candidate ID, public legal IDs, all actual choices/receipts, private truth evidence path/SHA, success bool/null, stop reason, steps, wall, inference count and endpoint hash. Missing matching call_vla cannot silently execute self (new regression). Restores include public cache/held/retry state plus simulator/controller/RNG/counters. Private labels never enter model requests. Optional sampling_seed is evaluated on the owned VLA server and preserves ordinary server RNG. PRO artifacts must NOT enter training or DevelopmentHistory.
4. Selection: higher observed rate, self on ties; unknown stays unknown; both-zero remains a task failure. Report optimistic sampled envelope/conditional rate product separately from independent full replay with fresh policy seeds; no claim that a product is measured full-task success. Full replay retains a shared10000sim/160decision budget. Startup {receipt['job']}_0 queued after cup startup9791, nice500/node02/one GPU; formal forty-case array NOT submitted until real same-launcher VLA physics and four exit-condition smoke are measured. No new physical result yet.
5. Latest original ec89f74 interim r17:106/133 physical completions /220 registered,0execution errors.87incomplete are not all queued; source/method-specific repairs remain separate. True-box9579 is20/20, kept separate. Cup band-seed source8410d77b startup9791 pending; original/cup/hybrid monitored by one controller. Current high-priority rf work is left untouched. Resource cap<=3; borrow4th only while C2 has no GPU job. No old held job release, no training.
"""
raw = message.encode()
path = Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md')
with path.open('ab') as stream:
    fcntl.flock(stream, fcntl.LOCK_EX)
    start = stream.tell()
    stream.write(raw)
    stream.flush()
    end = stream.tell()
report = {'time_pacific': datetime.now(ZoneInfo('America/Los_Angeles')).isoformat(),
    'start': start, 'end': end, 'sha256': hashlib.sha256(raw).hexdigest(), 'source_commit': 'e9aeaf9b'}
(base / 'reports/coord_hybrid_d2_append_20261019.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report))
