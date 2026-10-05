# Original stove control endpoint measurement probe

Prepare-only. Ten explicit original Goal task7 initial states (0–9), fixed initial→on→off sequence, 20 planned real contact calls. Each call uses the existing `V5Executor.vla_act` with 160 chunks, five controls per chunk and the unchanged 10,000-step episode ceiling. This is development selection, not a confirmation batch or a training-data producer.

Every phase saves its pre-recovery observation first, then explicitly releases and uses existing measured retreat before taking a fresh observation. Each observation independently queries `stove knob` and `stove switch handle` from both cameras, retaining all mask candidates rather than assigning a control pose from the stove-shell box. RGB, world point clouds, camera metadata, each mask/cloud, raw fit quality/orientation and coil packets have individual hashes. Missing current stove-shell measurements remain unknown; cached support is never used as current control visibility.

Read-only `turnon`/`turnoff` predicates and actual qpos are saved separately in `labels.json` for the same stationary observation. They do not select actions, change a pose, stop a VLA, determine when to retreat or construct a control endpoint. The existing finite-skill context allows the registered reverse-off action after original on-task native success; the native latch is preserved. Skill/recovery errors remain recorded. This probe does not modify the runtime or `probe_v5_skill501_original`.

Submission by the runtime owner, after the preparation files and final snapshot are synchronized:

```bash
SKILL_SOURCE=/public/home/sunyihan/rpent_libero_eval/<final-snapshot> \
  sbatch --parsable scripts/run_v5_stove521_endpoint.sbatch
```

Array `0–3%8`, one GPU per shard, no node binding or dependency. Output: `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove521_endpoint_original_20261005/probe_job<jobid>/part0–3`. Each part writes an `episodes.jsonl` ledger; each episode's three phase directories contain pre/post-recovery evidence packets and separate labels. The launcher records explicit producer hashes and requires stove module `b9dddb2d…`.

Preparation checks passed: module help, manifest validation, py_compile, bash syntax, and 22 focused stove/probe CPU tests. These checks establish the recording and fixed-sequence contracts; they do not establish physical success, SAM detection quality or off-verifier qualification.
