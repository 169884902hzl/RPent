# Codex3 bounded-skills development: b190f44

Simulation and CPU development only; no training, real hardware or leaderboard submission. Pushed to user-fork/harness-v5. Canonical spec: SKILL_PACKAGE_SPEC.md. Canonical schema: rpent/skill_package/schema.json.

## Source and interface

- Source snapshot: `/public/home/sunyihan/rpent_libero_eval/source_bounded_b190f44_20261016`.
- Archive: `rd-bounded-b190f44-code.tar`, SHA256 `4e8fed06fa4637e3e763a247fb5975cce7d95fe5b24d1529607ab71fad2e33c8`.
- Schema SHA256: `0da29ae7727d35c91083f3d0d2971cfbc8d91da6214b519c1202f388874d1de5`.
- Contract SHA256: `4690e01d91ea18b537984feab3fa513a08b974d8f8b98916cfb56d3ce7d9bc18`.
- Trajectory SHA256 **changed**: `e98827e0cd9ef55adf7a091dc6a784c48eb689faffbcaa9b19d8b9e38582452c`. Consumers must reload canonical source; do not retain an older loaded module with a new hash.

## Repairs and CPU evidence

174b742 retains one measured grasp patch during an approach and starts hold-coupling verification after closure. dfd0881 subtracts preserved per-view depth pixels rather than fused centroids, filters held payload/self geometry, rejects stale robot/budget/receipt contexts and revokes VLA success lost during handoff. fcdf0d8 uses static Panda visual hulls for self filtering and automatically inherits measured translational/angular v/a/j across motion/gripper/VLA controls. Missing derivative evidence remains explicitly unmeasured.

Jobs7579/7580 failed with `numpy.linalg.LinAlgError: Array must not contain infs or NaNs` after a successful descent. The fixed initial derivatives invalidate unrestricted rest-to-rest retiming. CPU reproduction with v=.005,a=.06,j=.6 and a .5m retarget produced the same numerical failure. b190f44 bounds the retiming search; nonconvergence invokes the existing continuous brake and replans from rest. Two regression tests verify clean nonconvergence and preserved initial derivatives through braking.

The new bounded oracle/model/VLA probe no longer consumes simulator object_names or instance counts to build perception queries. Queries derive only from the public instruction and static visual labels; detected entities still require RGB-D.

Focused checks: **72 passed**, one dependency warning. Command covers bounded_skills/async/screen/probe_resilience/motion/trajectory/vla/schema/exclusions and v5_branch_state/grasp_kinematics. This is CPU evidence, not category qualification.

## Physical evidence and runs

Preserved single-case jobs7572/7573 (source174b742) both publicly verified lifting a bowl, then failed the task because carry screening included residual payload/self pixels. K1 lift rise=.096075m, relative displacement error=.005777m; these are local grasp observations, not successful oracle episodes. Later jobs7575/7576 were stopped as development runs, retaining partial records. Jobs7579/7580 retain numerical failures.

Current replacement runs: **7581 oracle K1**, **7582 oracle K4**, same bowl state; **7583**, latest-source paired motion diagnostic on20 original states x3 routes. All use nice500, no node binding. Final category success remains pending. Historical expert original40 and explicit original90-adapter runs continue separately; Slurm completion is not task success.

The completed source84cf146 motion and pi0.5-only controls remain in PHYSICAL_PROGRESS.md and reports/. pi0.5-only215/220 is a control, not the bounded oracle upper bound. Old C3 K1 completed43/60 routes; K4 completed60/60. Do not transfer their metrics to the current derivative-aware executor before7583 is recounted.

## Exclusions and remaining dependencies

Runner consumes the pinned known permanent-state registry SHA256 `cb39016e573fbb43c123097ae4ddc8d0310ce0d17a1bdd977bc05e16b0b4dc22`:2165 identities and4 typed reservations. Each run saves state_exclusion_check.json. `coverage_complete=false` and `training_admission=false` remain explicit; this is not exhaustive history admission.

Conservative async adoption now rejects requests whose measured robot state, budget or receipts changed. This fixes stale-context acceptance but does **not** establish useful model/execution overlap. Codex2: please supply an actual bounded-choice endpoint with source/weight identity when available. The existing synthetic .9853s K4 P90 is not end-to-end HTTP or candidate-preparation latency. No replacement service or new training has been started.

VLA history stays n=0/null until source logs have complete admission evidence. Same-snapshot self/VLA fork recording is not yet physically demonstrated. No new freeze or collection qualification is claimed.
