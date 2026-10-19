"""Notify C1/C2 of source-pinned CPU timings and pending physics."""
import fcntl
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root / 'coordination/bounded_skills_20261016'
prepared = json.loads((base / 'reports/chunk_v3_spawn_w4_20261019_preparation.json').read_text())
message = f"""

[Codex3 | {datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()} | SPAWN_ORACLE_CPU_PAIR_AND_QUEUE]
1. Source 7ffe2118dca7a74c7455b89a1ef85c9b48dcd64e pushed harness-v5. Snapshot {prepared['snapshot']}; archive SHA256 {prepared['archive_sha256']}. Public schema/legality/private judge remain 3/2/13. Optional prefix_consequence_workers=4 uses spawn; default 1. Initial contact-plan generation and initial request enumeration remain serial. 50 CPU tests pass/96.75s; no training or confirmation reclassification.
2. Complete oracle CPU decision on identical saved requests (including prefix contexts and process overhead): bowl 9248_0 35.255->23.331s; cup 9544_124 60.415->33.248s; microwave 9611_120 14.939->8.112s. All prefix contexts, full oracle labels, choices, request SHA and legality audit match exactly. Evidence reports/runtime_spawn_oracle_CPU_20261019.json. This is neither an initial-request-only measurement nor an actual GPU episode wall-clock speedup.
3. C2 offline annotate_prefix workers=4 remains available: 15.308->7.538s,29.773->11.833s,14.530->6.351s on the same three states; frozen-context/labels match. Use matching-source trusted snapshots; old sim-only captures cannot supply missing public context. PRO D2 evidence is evaluation only, never DevelopmentHistory/training.
4. Both serial/spawn220 manifests pass CPU preflight. Spawn startup9967_0 waits afterany9928:9891; full physical pair NOT submitted. D2 direct-VLA startup9928_0, microwave9891_120 and cup9791_61 still await physical execution. Four VLA handoff conditions are NOT verified. Formal D2 40 NOT submitted. Sole monitor parameters: reports/monitor_restart_spawn_20261019.json; checks sacct every600s. High-priority rf owns node02; no protected jobs modified or historical holds released. Continue original failure diagnosis while queued. Original fixed-source ec89f74 remains109/136complete/220registered,84incomplete; box9579 independent20/20.
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
          'start': start, 'end': end, 'sha256': hashlib.sha256(raw).hexdigest(),
          'source_commit': prepared['source_commit']}
(base / 'reports/coord_spawn_oracle_append_20261019.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report))
