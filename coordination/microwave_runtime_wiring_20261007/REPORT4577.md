# 4577: runtime identity capture smoke completed; endpoint remains unmeasured

4577 COMPLETED 0:0 on node01, Slurm elapsed 6m02s, episode wall clock 358.355s.
One previously visited original LIBERO-90 task33/init0, development only.
No array release, qualification or training rows. Capture enabled; temporal stop disabled.

## Physical startup and provenance

- Same snapshot/launcher CPU preflight exit0: 651 indexed source files, 1/1 state hash.
- Snapshot import passed: identity constructor, OpenCV 4.11.0, SciPy 1.15.3.
- Live read-only chunk accounting observed 185 requested and executed controls.
- Final launcher physical_startup_contract.json: pass, 200 requested controls, 41 temporal records.
- Full final accounting: 40 chunks, 200 requested/200 executed controls, no infrastructure failure.
- Source: /public/home/sunyihan/rpent_libero_eval/source_v5_microwave_identity_runtime_20261008
- Source commit: 66e588fc892c15f5fddb3e047664fd0f05beb5c5, includes ca384ec/35e10e0/9cb4528.
- Archive SHA256: ddd89d8e3b296c65dd96a0f962ad0e5475e498b183f7436906a172b48268d510.
- Manifest: results/harness_v5/microwave_identity_runtime_CPU_20261008/r1/capture_identity40.json
  SHA256: 91006135d52ae712519b4289d1997106f0a17be1ef824e215c7017039d8faf45.
- Output: /public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave_identity_runtime_original_20261008/capture40
- Delivery: /public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave_identity_runtime_CPU_20261008/r1/delivery_manifest4577.json
  SHA256: 0f4dd6f10950736857718391c1803d1891ebc9ab94b47bac092849f4955e670c.

## Public measurements

42 public RGB-D capture instants: 2 baseline and 40 post-chunk probes.
Both baseline frames passed the public capture-pair checks.

| Probe metric | Agentview | Wrist |
|---|---:|---:|
| Current fixed frame present | 40/40 | 2/40 |
| Current moving plane present | 35/40 | 0/40 |
| Newly recovered tracked cloud | 0/40 | 0/40 |
| Attempted temporal identity recovery | 1 | 0 |

The five missing door measurements are blocks 34-38 (source steps 36-40).
At block34, the previous mask supplied 157 image corners but zero mutual
forward/backward correspondences. Fixed-frame angle change was 0.0000012 degrees
and normal drift was zero. Thus this particular loss occurred before robot-mask
filtering or fixed-frame stability rejection. The next four frames correctly
cleared history; the runtime did not bridge an unobserved interval.

Wrist measurements did not supply a door cloud in this episode. Missing wrist
frame/door identity therefore prevented wrist tracking, rather than an exception.
The optional sample field currently says "independent" when a tracking record
is absent, even if the door is missing; the counts above use actual cloud
presence, not that diagnostic label.

33 probes reported non-endpoint, 5 lacked independent door/mask evidence, and
2 yielded close candidates: block39 at 3.981 degrees and block40 at 3.195 degrees.
The two candidates span only 5 executed controls = 0.25s. The original 0.3s
stability check correctly withheld withdrawal/confirmation. No after pair or
temporal stop was admitted. Final receipt: articulate_verified=null, chunk_budget.

Private labels were attached only after the public summary was saved: initial
close=false, final close=true, native success latched=true. Physical closing
and public endpoint verification are separate results. This is one correlated
development trajectory, not a confirmation success-rate estimate.

## Next Executable Work

1. A bounded stop-enabled smoke on the same visited state can use max_chunks=48.
   This leaves space for a third independently measured stable candidate and
   the original withdrawal/two-frame confirmation, without changing thresholds.
   Keep it marked development; changing its budget is not a causal comparison
   or qualification. Retain 4577 unchanged. Inspect rollback after withdrawal.
2. Identity tracking itself remains insufficient. The earlier dense4550 run
   lost identity even with 0.05s captures, so increased capture frequency alone
   is not a supported remedy. Reuse robots/libero/v5_temporal_verifier.py's public
   RGB-D sequence/proprioception encoder for a separately trained microwave
   endpoint verifier; add missing-view/occlusion features, with simulator joints
   only in labels. Reserve train/validation/confirmation states before collection.
3. The first CPU implementation and explicit data adapter are estimated at
   1-2 hours. At this smoke's 6-minute/state throughput, 200 fresh states are
   about 20 GPU hours before qualification; dense 4550-style collection is about
   32 GPU hours. These are scheduling estimates, not submitted runs or scores.

The preparation code now recomputes source_snapshot_sha256 when replacing an
inherited source identity. Its focused test passed. This metadata-only repair
is after 4577 and does not mutate that immutable snapshot or retained manifest.
