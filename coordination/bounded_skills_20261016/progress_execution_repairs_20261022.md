# USER 10/21 09:00 execution repairs

Authorized: F1–F6 execution repair; CPU actual N1 diagnostic subsets first, full CPU; same-complete-initial19 regressions then full N1 30; after N1 target redo original90 self>=2 and initial-pose>=3, D2 40x0/1/2; own original-train perturb generator,20pi pilot then60labels. No training. PRO/D2 eval only, permanent confirmation exclusions unchanged.

Resources: only node02/nice500; <=3 GPUs, optional4 only no C2 demand, total CPU+C2<=80/memory600GB. Protected p3/c5/c6/rf/RVRT and old held untouched. Live at start p3-agent-select11131_3 occupies1GPU/16CPU; C2 fit11137 now1GPU/4CPU. Two currently available GPUs.

Implementation in progress; no physical result yet. HEAD3d3edbb6 with pre-existing unverified point-SAM cache only in dirty bounded_skills/test file. Its exact pre-existing patches preserved /tmp/execution_fixes_20261022_preserved; must exclude these from commit/archive.

Actual failure diagnostic rows exported from optimized N1 case001(container s0),002(stove s0),006(bowl s2),007(container s2),027(object_swap). Exact source loop and public screen/receipt subsets in tests/unit_tests/robots/libero/fixtures/execution_zero_step_receipts_20261022.json. This is a diagnostic subset, NOT full cloud or a re-created physics proof. Main raw loop path ROOT/results/bounded_skills/schema6_20261020/N1_strict_645c4d22_r1/optimized/caseXXX/loops.jsonl. Full original initial sources remain frozen.

Modified: screen rebase per actual skill/brake measured pose; per-box minimum instead of point-id rule; connected-support payload clearance for lift only, non-lift remains pairwise; motion retry routes same capture/internal cap13; preparation4same-endpoint paths; null all failed zero-step expectation checks; pending grip preserved; no recovery/progress charge for zero-control planner receipts; ask_help attempts reverse actual executed trace+refresh. Full contact sequence conditional precheck (ingress/closure/initial lift or wrist turn) being added, still needs tests/physics. Stage counts/numerics not yet validated.

4 new diagnostic subset regressions passed. Screen+chunk58pass/1old oracle-expectation failure; updated old test to new user-required zero-step-grip behavior. CPU full r1 currently running but source changed afterward; do NOT claim exact archive passed from it. Need finish changes, precise staged archive (exclude old SAM cache), exact CPU then physical19.

Continuation: exact commit `03552c03bf2f89fcc45163c9561457904c1372fe` archive
`/tmp/rd_execution_03552c03_20261022.tar.gz` SHA256
`901d513b7c454eb8a853f6c68700919b6ee5427770406dad0c391e3a81fc1cf3`
passed the CPU panel: **734 passed**, 6 warnings, 300.28 s; log
`/tmp/F_exact_03552c03_CPU_20261022.log`. No pre-existing dirty SAM-cache
patches are in that archive. Launcher CPU preflight passed after supplying
its required checkpoint environment variables (the earlier manual preflight
omitted them and exited 1 before simulation).

Submitted physical regression jobs **11141 / 11142**, node02, nice500,
one GPU / 12 CPU / 100 GB each. Registered 19 indices are split 10+9 in
`ROOT/results/bounded_skills/execution_repairs_20261022/03552c03/preparation/regress19.json`.
Both use the unchanged complete common starts from strict N1. The first
startup physically executed container s0 move_to: success, 264 controls;
this is startup evidence only, not a closed episode or a recovery-rate claim.
Full 19 and 30-pair results remain pending.

First physical feedback: container s0/s1/s2 all close with a nonempty
aperture, then lift is rejected before control by
`measured_support_separation_decreased`. In s0 the second sampled pose moves
up by 0.26 micrometres while tangential drift changes the nearest depth
sample, reducing unsigned sampled distance by less than 1 micrometre. This
is not a proof of payload/support penetration. CPU correction fits only a
locally planar occupied depth patch and tests signed separation along its
measured normal; nonplanar/unfitted obstacles keep the exact point-cloud
check and 4 mm clearance. Decreasing signed clearance still rejects. Added
an opt-in diagnostic launcher capture of exact failed public support route
inputs (not enabled for final latency comparisons). Focused screen,
receipt and launcher checks: 43 passed. Exact new-snapshot CPU/physics still
pending; first-round failures remain intact.

Exact `2e3a401a` archive SHA256
`4175068bd3842fac9e6affc466fb8c0e803b6728a377d89c188c0304788ff07d`
passed **735 CPU tests**, 294.61 s; log
`/tmp/F_exact_2e3a401a_CPU_20261022.log`. Round 2 jobs **11143/11144** use
the same 19 indices/common complete initial states, each after its round 1
shard. Diagnostic failed-support input capture is enabled in round 2, so its
timings include serialization overhead; final latency regressions disable it.

First interim strict pairing (15/19 closed, not the full 30): original
baseline 15/15 versus round 1 1/15. All 15 complete physics/controller/RNG
initial hashes matched. Per-decision four-stage medians (seconds): baseline
28.188 / 60.714 / 16.553 / 8.090; round 1
0.455 / 4.486 / 3.077 / 0.714, in perception/candidates/decision/execution
order. The lower runtime coincides with many zero-control failures; it is
not an accuracy-preserving speedup. Raw paired records:
`ROOT/results/bounded_skills/execution_repairs_20261022/03552c03/interim_pairs_v1/`.

Own-layout CPU prototype: geometry/admission unit checks **7 passed**.
`scripts/generate_bounded_train_layouts.py` rebuilt the final original-train
goal witness in an independent renderer-free CPU simulator by replaying 27
saved original controls. First generated bowl state, seed **11020000**,
native predicates feasible and no object penetrations in initial/witness
states. Exact private generated-state SHA256:
`88f06bdf0e62f992bc440798a9bb1c788a6a7260835c3466ab474e77d51b5490`.
Remote registration/output: `ROOT/rd_train_layout_CPU_20261022/`;
local metadata: `coordination/bounded_skills_20261016/preparation/train_layout_CPU_20261022/`.
Seed segment 11020000–11029999 was recorded before the CPU generation.
This is **not training-admitted**: exhaustive geometric confirmation-distance
checks and additional asset distractor insertion remain pending; no GPU
pilot/labels have run, and no PRO/MAX inputs were used.
