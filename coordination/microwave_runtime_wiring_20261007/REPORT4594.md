# 4594: stop-enabled microwave development smoke

Job `4594` completed `0:0` on `node02` in 6m55s. It reused the immutable
source from 4577, ran one previously visited original `libero_90 task33/init0`,
and changed only `max_chunks` from 40 to 48 plus `microwave_temporal_stop_v1=True`.
Thresholds, public inputs, task state and training boundaries were unchanged.

- Source: `/public/home/sunyihan/rpent_libero_eval/source_v5_microwave_identity_runtime_20261008`
- Commit: `66e588fc892c15f5fddb3e047664fd0f05beb5c5`
- Manifest: `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave_identity_runtime_CPU_20261008/r2/stop_identity48.json`
  SHA256 `74d03daab9b504b9cc786b8dd1831ebde7029f3c24cfbfd28f3872b514e7606f`
- Output: `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave_identity_runtime_original_20261008/stop48`
- Delivery: `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave_identity_runtime_CPU_20261008/r2/delivery_manifest4594.json`
  SHA256 `0345fce9df1648536ed3a119f580488ed1ab435e89221a6a11d37eed85d17dd8`
- CPU preflight: same launcher exit0; actual startup contract `pass`.
- Physical accounting: 240 requested / 240 executed controls, 48 chunks, no infrastructure failure.
- `qualification=false`, `train_allowed=false`, `new_training_rows=0`.

Public capture contained 50 frames: 2 baseline and 48 probes. Agentview had a
current fixed frame in 48/48 probes and a moving plane in 41/48. Wrist had a
fixed frame in 1/48 and no moving plane. Identity tracking recovered one current
agentview cloud. Tracking attempts recorded two `mutual_door_correspondences_missing`,
one `current_depth_plane_with_tracked_door_identity`, and one
`current_door_depth_support_missing`. There were 39 non-endpoint probes, 7
unmeasured probes, and 2 endpoint candidates (chunks 35 and 41). Neither
candidate had a second stable candidate after it, so staged confirmation never
admitted withdrawal or stop. The final public receipt was `verified` from the
post-contact path, while temporal stop count was 0; these are separate metrics.

The 48-block budget did not solve the identity gap. At chunk 34, only one mutual
track remained; at chunk 36 only seven and at chunk 47 only five current depth
tracks. A later chunk 44 succeeded with 90 visual tracks but only 12 current
public-depth tracks, enough for one tracked fit but not a stable endpoint pair.
The remaining issue is current RGB-D support under the changing door view, not
fixed-frame drift or private state. No threshold was relaxed. The next useful
fix is a separate public temporal verifier using RGB-D sequence plus proprioception,
with missing-support as an explicit feature and simulator joints used only as
training labels; do not use stale masks to bridge missing frames.
