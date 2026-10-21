"""Deliver the complete strict-N1 latency result and current B2 run pointers."""
import fcntl
import hashlib
import json
from pathlib import Path


ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
message = '''
[Codex3 | USER10/20 22:40 continuation | B2 ON for development]
B2 three-consumer compatibility ACK is now observed at /public/home/sunyihan/rd_instruction_20260923/c2_retrain_20261020_2240/B2_THREE_CONSUMER_ACK.json. No trained-service readiness is inferred. C3 original train state registration and D2 oracle development proceed without another ACK gate. Current immutable D2 source source_B2_1a7ca238_20261021; recovery0/1/2 outputs results/bounded_skills/schema6_20261020/B2_1a7ca238/D2_recovery{0,1,2}/. 11061/11062 running; 11063 cancelled only to return borrowed GPU, three closed cases retained and remaining cases will resume. C2 GPU11066 was RUNNING33s after watcher first observed demand, so C3 uses at most3 GPUs.
Complete C7 strict result: results/bounded_skills/schema6_20261020/cpu/N1_strict_645c4d22_C7_r3/manifest.json and paired_states.jsonl. 32 registered =30 whole episodes +2 continuation pilots, not32 task outcomes. Independent complete saved initial physics/controller/RNG digest30/30 matched. Baseline6a2d6bb8+D3 success25/30 versus645c4d22 success7/30;1 improvement,19 regressions. Container8/8->0/8, stove_on7/8->0/8; accuracy is not preserved. Per-decision median seconds perception18.866->7.488, candidates63.403->9.268, decision14.717->3.284, execution4.327->1.084; decision includes oracle successor legality14.548->2.850. Full loop104.276->21.131; episode333.929->235.047. Nested/column medians must not be summed. New3f N1 stopped after8 closed because contact-screen regressions reproduced; all attempts retained.
11025 full cProfile confirms build_obstacles6 calls/2.598s, _cloud_and_ik96/79.897s and _instance_pixels48/58.447s. These cumulative times overlap.96 calls do not mean96 obstacle-index builds. Remaining instance/payload measurements are under investigation; no new unsupported cache speedup claimed.
Original B2 labels source source_B2_labels_cb116d1e_20261021, commitcb116d1ef69d5d5e2bf1d0ac31bb33a8f867ee4c, exact archive CPU707 passed. Registration11067 selects nine original train categories x10 independent initial identities, preferring intermediate/held states; first30 bowl/box/cup. Each state registers self1 and in_place/initial_pose/full_task3 each. Stove tasks remain frozen task_holdout and are excluded. Pending registration/physical trials are not delivered labels. C2 rotate_wrist/align missing-task list received; no heldout task is moved into train. D2/PRO and permanent confirmation exclusions remain unchanged; C3 does not train.
'''
path = Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md')
receipt = ROOT / 'coordination/bounded_skills_20261016/reports/B2_C7_coord_delivery_20261021.json'
raw = message.encode()
with path.open('ab') as stream:
    fcntl.flock(stream, fcntl.LOCK_EX)
    start = stream.tell()
    stream.write(raw)
    stream.flush()
    end = stream.tell()
with receipt.open('x') as stream:
    json.dump({'path': str(path), 'append_start': start, 'append_end': end,
               'sha256': hashlib.sha256(raw).hexdigest()}, stream, indent=2)
print(receipt)
