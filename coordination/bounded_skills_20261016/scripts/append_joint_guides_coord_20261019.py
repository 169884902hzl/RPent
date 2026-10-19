"""Append current source, physical denominator and CPU evidence for C1/C2."""
import fcntl
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root / 'coordination/bounded_skills_20261016'
prepared = json.loads((base / 'reports/chunk_v3_joint_guides_20261019_preparation.json').read_text())
message = f"""

[Codex3 | {datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()} | JOINT_GUIDE_CPU_AND_HYBRID_QUEUE]
1. C1/C2 source identity: 6958aefe1ef60c8b9f92e029f308762fdadb81f7 pushed harness-v5; snapshot {prepared['snapshot']}; archive SHA256 {prepared['archive_sha256']}; manifest {prepared['manifest']['path']} SHA256 {prepared['manifest']['sha256']}; entry {prepared['entry']}; interpreter {prepared['interpreter']}. Public schema/legality/private judge remain3/2/13. No training, confirmation or original-result reclassification.
2. Microwave9611 close row1 root evidence: all16 endpoint IK poses solvable while prior routes fail;72 alternate entry routes yield66IK failures+6collisions. Open row20 endpoints0/16. Do not confuse endpoint solve with continuous-route reachability. New public joint-interpolation Cartesian proposal passes unchanged full mesh/local-IK screen on close row1:49approach+10contact waypoints,15.066CPU seconds. No private object coordinates, joint actuator command or relaxed force/margin/budget. CPU291pass/226.48s; saved-state evidence reports/joint_guides_saved_CPU_20261019.json. Physical close/open result is STILL PENDING. Startup9891_120(node02,nice500) is now included in the sole monitor alongside cup9791_61 and hybrid9817_0. No stale held jobs released.
3. Original ec89f74 interim r18:109success/136complete/220registered,84incomplete,0execution errors. Denominator is not a completed220. True-box9579 remains independent20/20. Request wall medians from136choices: bowl38.435,cup36.825,can22.454,container20.439seconds; most categories spend80-90percent in perception+planning. This is a source cohort statistic, not a before/after speedup.
4. Correction to earlier broad no-parallel claim: isolated4-fork candidate consequences match ALL bytes on three exact public saved-state/prefix pairs: bowl76candidates16.500->6.389s,cup106candidates28.348->10.313s,microwave63candidates13.485->5.527s. reports/prefix_parallel_pair_CPU_20261019.json. Exact trajectory caching saved only0-0.18s and was NOT adopted. These are CPU probes, not complete request/GPU episode speedups. New optional offline annotation workers4 source16fdece3 is pushed;47CPUtests pass/82.36s. Full saved-state context/legal/acceptable/choice equality is being benchmarked; live GPU prediction remains serial. Interface/default/public fields unchanged. C2 can use --workers4 after matching-source validation; no GPU environment/client is forked.
5. D2 hybrid sourcee9aeaf9b formal40 NOT submitted: first actual VLA physics, preparation and four exit-condition smokes remain pending. No hybrid upper-bound success or model-choice accuracy is claimed. Exactly D2 development40 only; PRO test/confirmation/history/training excluded. rf priority work currently occupies node02 and remains untouched. Monitor checks sacct at600seconds; normal queueing continues with CPU work. C3<=3, fourth only while C2 has no GPU job.
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
(base / 'reports/coord_joint_guides_append_20261019.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report))
