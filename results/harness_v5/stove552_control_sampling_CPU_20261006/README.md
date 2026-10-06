# Stove552: current directed-control sampling, CPU preparation

This packet prepares a new original-task measurement run. It neither submits a
GPU job nor establishes a verified `turn_off` endpoint. Existing SOURCE550 and
job4186 remain independent records.

`stove_control_sampling10.json` keeps the original Goal task7 init0–9, fixed
initial/on/off sequence, 20 contact skills, 160 chunks × 5 actions per contact,
and 10,000-step episode cap. With `stove_control_features_v1` enabled, each
on/off contact additionally has a before-contact capture. Initial, on and off
produce 8 captures per episode: 80 captures and 160 camera views in total.
Each capture saves both calibrated RGB-D views, metadata, all SAM masks/clouds,
and file hashes. Every view uses the two original control queries and four
explicit feature queries: pivot, tip, shell and front edge.

The public binding requires a unique current control attached to a stove
measured in the same capture. A lever direction requires distinct pivot and tip
measurements; a stove reference requires distinct shell and front-edge
measurements. Repeated masks, missing masks, ambiguous instances, insufficient
depth and out-of-bounds components retain an explicit reason and null direction.
The contact PCA is an undirected axis only. Even when both directed features are
available, the endpoint remains `unmeasured` until independently calibrated and
confirmed. Private qpos and predicate labels stay in separate `labels.json`
files; they do not select captures, actions, binding or public geometry.

The five explicitly listed original job3679 control clouds replay successfully
as current control poses. All five lack separately measured pivot/tip and stove
front-edge features; all remain `unmeasured`. Reversing point order does not
create an endpoint. The 61 focused CPU checks cover missing and ambiguous
features, parent binding and the existing endpoint semantics. These are software
checks, not physical skill qualification. The original run had 60 captures and
120 views, only five valid control poses, all from post-recovery wrist views.

Rebuild this CPU packet from the repository root:

```bash
PYTHONPATH=. .venv/bin/python results/harness_v5/stove552_control_sampling_CPU_20261006/build_cpu_packet.py
```

After the owner registers a new immutable source snapshot and launcher, the
probe command for each of four shards is:

```bash
export PYTHONPATH="$STOVE552_SOURCE" MUJOCO_GL=egl PYOPENGL_PLATFORM=egl LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH=/public/home/sunyihan/rpent_libero_eval/runtime_config
export PI05_CHECKPOINT_PATH=/public/home/sunyihan/rpent_libero_eval/assets/pi05
export SAM3_CHECKPOINT_PATH=/public/home/sunyihan/rpent_libero_eval/assets/sam3/sam3.pt
cd "$STOVE552_SOURCE"
/public/home/sunyihan/rpent_libero_eval/.venv/bin/python -u -m scripts.probe_v5_stove521_endpoint \
  --manifest /public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove552_control_sampling_CPU_20261006/stove_control_sampling10.json \
  --shard-index "$SLURM_ARRAY_TASK_ID" --shards 4 \
  --output "$STOVE552_RUN/part${SLURM_ARRAY_TASK_ID}"
```

The old `scripts/run_v5_stove523_full_chunks.sbatch` hardcodes the old manifest
and output directory; it is not the launcher for this packet. The owner must
register the final source hashes and choose an output directory before any
submission. No node binding is required by this packet.

`nearzero_physical_selection_proposal.json` is a separate prepare-only proposal,
not an implemented sampling driver. It fixes two methods, all ten original
initial states, and off-prefix chunk counts 1/4/16/64/160 with a fresh reset per
cell. Near-zero true-off and intermediate-dark bins are assigned only after
collection using private labels. The proposal targets at least 20 distinct
observations in each bin, retains every observation, and does not adapt capture
timing to qpos, outcomes or verifier verdicts. A fixed-prefix/reset-method driver
extension is still needed. Insufficient coverage must be reported; this proposal
does not authorize qualification, training or extrapolated `off=True` labels.

`manifest.json` lists every packet input/output and the changed source/test
files explicitly. Replays read only those paths; they do not enumerate artifacts
or open PRO assets, sealed instructions or manual test files.
