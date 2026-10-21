# USER 10/21 09:00 execution repairs

## 10/22 continuation after attached-object probes

LATEST: ordinary closure/lift removal N1 job11193 is fully closed **20/30**
versus baseline25/30, improvement1/regression6, all30fullinitial hashes match.
Exact source tree7bfd88d4, archivecbe79609. Artifacts remote
`.../object_contact_ablation/N1_30/closed30/`, local
`reports/object_contact_ablation_20261022/`. Four-stage medians3.469/5.393/
2.062/.803s, loop12.168s, episode112.228s; many zero-control failures prevent
an accuracy-preserving speedup claim. All three shards COMPLETED0:0.
N1 not qualified, so NO repaired90/D2/perturbed collection has started.

Bowl s5 exact public CPU replay now matches collision pose and9rightfinger
target points. Existing eager search on identical retained measurements finds
another route-screened grasp `s5_a0_top_distal_pad_edge_cell`; not physical
success evidence. Original near-duplicate retained masks haveIoU.99634;
replay logs the choice and still asserts exact collision pose/counts.
Script `bisect_N1_contact_chain_CPU_20261022.py --compare-grasp-search`;
r1diagnosis failed on mask ambiguity and is preserved; r2succeeded.

Physical bowl s5:99d90ae8success3dec/540steps and3d3edbb6success4/745,
both complete initialSHAe11acfa9812cb9b603fcd54fd9a82e87b4cc731645771d4a343bdadb57fbe772.
Comparisons are11198(99d→daaa) and11200(3d3→03552), child arms still pending
at this update. Container s6 parent99d success2/600, initialSHA
c2623466ccabc00d4043533d4af1c45ef6a748b57d99f021f50ed3427c99deff;
childdaaa is11202_1. Do not count pending/interrupted diagnoses as full failures.
11191_0closed spatial_swap26success665steps, object_swap27success343steps,
object_task29failure347steps.11191_1was cancelled after reproduced zero-step
descend trap on26 and subsequent repetition, no closed result.

New **uncommitted ablation**, not an asserted fix: ordinary move execution
no longer gates a collision-screened standoff on a future unexecuted descent;
actual move/descend collision checks and fixture coupling stay intact.
Working bounded_skills contains this plus the older unrelated dirty SAM
cache; do NOT stage the SAM hunk.3new fixture/object behavioral tests pass,
focused32pass. Exact counterfactual tree3c6bc6bfa00bad7d0a154136042faa8e49a6e8e3,
archive82ce2f0a7df2387c17e2f73bf09e1a5e0d4b63e0bd91eb6716f96dc26f9792e6.
Local/tmp/rd_standoff_ablation_source_20261022; remote
source_standoff_ablation_20261022. Full CPU running session11805,
log/tmp/standoff_gate_ablation_exact_CPU_20261022.log. Then same-state
index15/1/6/2 probes before any further full30.

Post-N1 preparation only: commit4ea1fcab uses registeredworldXY5cm metric
(not3Dcentre distance),10tests pass; aa433ad9 adds explicitly registered
self_repeats, same branchpoint restored per trial,49focusedtests pass.
Both commits pushed. Full native-buffer+sampler exact aa433 source CPU697
pass309.30s; archiveSHA4c59f08ec83b72d798d51705d681c48cca7f41f407e1b03e96e91af6637936e2,
remote source_postN1_aa433ad9_20261022. This source is NOT physically admitted
and must not be used for90/D2 before N1 qualification. Permanent geometry
exclusion remains pending in the layout CLI; prototype training_admission=False.

Snapshot `05143337`, archive SHA256
`1f672177a952f15fa9585b9129b9331743cd81e8bb1d2cb4fe05ffa0b6de7e40`,
passed exact CPU761 and the three physics probes: container index1 (596steps),
bowl index6 (261steps), stove index2 (676steps). Complete N1 job11181 closed
all30: baseline25/30, attached snapshot18/30, improvement1/regression8.
All registered complete initial hashes match. Four-stage medians per decision
(perception/candidates/decision/execution seconds): baseline
18.8661/63.4034/14.7172/4.3271; attached1.6653/5.0122/2.0750/.7065.
Whole decision loops104.2759→12.0273s, whole episodes333.9287→112.6007s.
Oracle successor annotation is14.5480→2.0604s of the decision phase, not
model inference. This is not an accuracy-preserving speedup. Full evidence:
`results/bounded_skills/execution_repairs_20261022/05143337/N1_30/closed30/`;
local reports under `reports/attached_05143337_20261022/`.

New bowl index0 first-bad edge is physically proven: parent3d3edbb6 succeeds
291steps/2decisions, child03552c03 fails23steps/8decisions. Both complete
initial SHA `9a9cb2f45cce0ea2d27c79aefa910135651a87b1823f56f4055f5131574e6ddf`.
Jobs11186_0/1 completed0:0; exact CPU panels657/661pass. The saved public-input
replay isolates accepted approach/ingress versus rejected predicted initial
lift. Probe sources retain production code with accepted D3 transport only.
11184 was a manifest trailing literal-newline error before physics; fixed
11186 preserved those logs. Old daaa bowl job11164 was cancelled after >100
loops without closure; it is an interrupted diagnosis, not a scored result.

Production commit139431e9 removes ordinary-object pre-grasp closure/lift
expansion; actual descend/lift collision checks, fixture coupled-turn checks,
and F4 null/pending-grip semantics remain. Focused29tests pass. Strict ablation
tree `7bfd88d4b5942732cc6369994cd157ccd46305ca` is05143337 plus only this
two-file diff, excluding the newer D2 transport and the dirty SAM point cache.
Archive SHA256 `cbe796095ea123c0cc3a05ce85b6300fe78883b23186acd2cd6154501a927070`.
Exact CPU panel running, then index0 probe and full30 if that probe passes.
Other object probes26/27/29 compare99d90ae8 anddaaa1730 using existing exact
CPU-validated sources; job11188, nice500/node02, two GPUs. Codex2's11173
remains untouched; total C3 concurrent use stays at most3.

D2 audit now closes all245 unavailable variants:144first binding-missing
early exits,26binding-lost-after-recovery exits,18placements lacking public
held identity,50public terminal catalogs,7region/target mismatches. The last
seven bind internal cabinet top_region to exterior top-surface e82; the
current in catalog uses container identities including parent e118. No
PRO-specific binding rule has been added. `a06f3e00` fixes the unbound
fallback path (first170 cases) using existing legal public options and
records actual fallback mode/scoring scope.

Native-success endpoint loss: CPU replays112original controls with zero
integration residual; forward alone changes official On=False. Capturing and
restoring original native MjData buffers restores True byte-for-byte. This is
CPU evidence, not a new D2 GPU rate; exact a06f3e00 CPU764pass.
The22 sampling/replay gaps are individually attributed in
`reports/attached_05143337_20261022/D2_replay_gap_{table.md,rows.json}`.
Counts4handoff completion lost,3native endpoint phase lost,5replay block
budget,3public-vs-private-v3 grasp disagreement,1no-progress stop,
5variant unavailable after partial replay,1own guard/observe collision.
Old D2 rates8/40,16/40,15/40 remain unchanged. New120 remain after N1 target.

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

Round 1 closed: **2/19**, Wilson95 [0.02936, 0.31394], paired original
baseline **19/19**. Categories: container 1/8, stove_on 0/7, bowl 1/2,
object_swap 0/1, object_task 0/1. All complete initial hashes verified.
Closed evidence: `ROOT/results/bounded_skills/execution_repairs_20261022/03552c03/closed19_pairs/`.
Receipt audit: 166 receipts, 124 unsuccessful zero-step receipts, 83
zero-step planner rejections; all 8 zero-step lift held checks are null.
Exact audit script `/tmp/audit_execution_receipts_20261022.py`, remote ROOT
copy; output `.../03552c03/closed19_receipt_audit.json`.

Round 2 at the inspected checkpoint: 15 closed, 1 success, 14 failures,
therefore full30 upper bound **16/30** even if every remaining state succeeds.
Both rounds are conclusively below20; commit bisection starts, while the
complete round2 N1 continues. Remaining11 job **11145** waits for11143/11144;
11144 already completed0:0. Failed support route exact public input pickles
were saved and CPU-replayed with identical failure reasons. Their plane fit
count is **0**: the local patch fails planarity criteria, so the plane-only
fix does not address these real inputs. Do not call that repair effective.

Bisection midpoint **93c1213cc33c318c52b487f97b07c326fde60382**, 3 probes
indices1(container),2(stove),6(bowl). D3 transport-only overlay is identical
in meaning to accepted baseline6a2d+D3; branch state file SHA
`b26296a7c11d1919f3f1d977f65cadcff147fad2633cb45645c33d0c4ed55e05`.
Local `/tmp/rd_bisect_93c1213c_D3_20261022`, bundle SHA
`8b539362fa53f55eeb505d30923f0607add2a9c513939996c52b274a7e0a9011`.
Remote `ROOT/source_bisect_93c1213c_D3_20261022`; CPU panel running in
session25958, log `/tmp/bisect_93c1213c_D3_CPU_20261022.log`. Not yet physical.

CPU stove isolation used actual original saved annotation
`ROOT/results/bounded_skills/feasibility_20261017/job9248_10/stove_on_libero_goal_t7_s0_oracle_k4/private_prefix_state_0000.pkl.gz`, SHA
`e9730648686bc6f31acf4dd77784c5ba59d3ba7c710f931bfcb850abae595cfc`.
Explicit above/over passes current source at6.944mm clearance,564 predicted
steps; merged schema6 on the SAME saved measured plan rejects the ingress
against one rightfinger target point, then returns failed left/around.
This isolates a planning/guard difference without new SAM/RPC or physics.
Output `.../2e3a401a/CPU_stove_saved_plan_schema6_r2.json`. It is not a strict
N1 whole-episode replay and does not establish the first bad commit yet.

Additional supported F4 bug: successful wrist-scan withdrawal unconditionally
clears a nonempty pending object grip, after which oracle opens it. Working
patch preserves pending identity while calibrated aperture excludes empty
jaws; it never claims held=True. Targeted9 tests passed. **Uncommitted,
not in any GPU snapshot**, pending bisection integration. Pre-existing dirty
SAM-cache diff before this new edit is saved
`/tmp/pre_pending_grasp_cache_20261022.patch`; exclude it when staging.

Round2 19 closed: **2/19**; remaining11 continues as11145. Binary midpoint
93c1213c+D3 CPU panel passed626 test executions (RGB-D file was explicitly
listed as well as included in the glob), log above. Physical job **11147**
passed real startup. Container probe failed; stove probe also reproduces
descend31-control braking rejection then zero-step trapping. Thus the first
regression in the three-probe diagnostic lies before/equal93c1213c, rather
than in the later support-plane patch. Next midpoint **b1365785** is preparing
under `/tmp/rd_bisect_b1365785_D3_20261022`, exact archived CPU panel session
77819; no physical submission yet. No production skill source is patched in
the bisection archives; only the already accepted complete D3 transport and
the recorded launcher are overlaid.

Failed patch geometry is now quantified at `.../2e3a401a/support_patch_diagnostics_CPU.json`.
Container s0 support component has167 points, median plane residual0.122mm
but maximum9.78mm; some other initial-contact components are isolated
one-point fragments. Other container patches mix points from table level
to14.6cm height. This explains why the strict single-plane fit yields zero
planes. These are observed public geometry diagnostics, not new relaxed
collision rules or ground-truth support assignments.

Corrected closed N1 indexing: bounded cases are 0–23 and 26–31; 24/25 are
VLA continuation pilots and remain separate. Earlier `closed30_pairs` was
actually 28 bounded pairs; it is preserved and superseded by
`.../2e3a401a/closed_correct_bounded30_pairs/`. Missing jobs11152/11153
completed0:0, yielding exactly **30 bounded pairs + 2 separate pilots**,
no missing cases. All complete initial physics/controller/RNG hashes match.
Baseline **25/30**, Wilson95[0.6643564949358397, 0.9266345762815146]; round2 **2/30**,
Wilson95[0.018477023791270378, 0.2132345836261692]. No improvements;23 regressions.
Local evidence: `reports/execution_repairs_round2_correct30_20261022/`.
Per-decision four-stage medians, seconds:

| Arm | perception | candidates | decision | execution | whole loop |
|---|---:|---:|---:|---:|---:|
| before | 18.866 | 63.403 | 14.717 | 4.327 | 104.276 |
| after | 0.436 | 4.181 | 2.810 | 0.649 | 9.634 |

Faster timing accompanies zero-control failures and **is not an accuracy-preserving
speedup**. The oracle-successor legal calculation median is14.548→2.790s;
this diagnostic computation is distinct from future model inference.

Bisection b136 probes now all closed: container idx1 succeeds2decisions/595steps;
bowl idx6 succeeds3decisions/261steps; stove idx2 fails32decisions/711steps.
Therefore container/bowl and stove have separate brackets. Container bracket
good b136→bad93c; midpoint7f852aeb+D3, exact CPU619pass, submitted as11157.
Stove bracket good6a2d6bb8→badb136; midpoint2b64eda3+D3 preparing.
All production skills/planning/perception remain original per bisection source;
only recorded complete-state D3 transport and launcher are overlaid.

Pending-grip wrist-observation fix is now committed/pushed as edd067fb, exact
staged9tests pass; it has no physical result yet. Own-layout language-identity
v2 CPU checks9pass are dirty/uncommitted; no v2 state has been generated.

Continuation evidence (10/22): container7f probe11157 succeeds2decisions/595steps;
container99d90ae8 probe11160 also succeeds2decisions/595steps. Parent99d bowl
probe11161 succeeds3decisions/261steps. Container first326 action+public
proprioception trace SHA is identical for7f and bad93:
`701f0c9a355fce0f19537a2926ad217faaf1774c49f79cedd379f67b7b4a5bd7`.
The later bad lift is an unexecuted finger-shell collision, overwritten by
`public_hold_not_verified`; current F4 already prevents that overwrite.
Parent99d→childdaaa1730 is now the container/bowl diagnostic edge. Exact CPU
99d559pass; daaa562pass. Child container11162 and bowl11164 (verify submitted
ID in remote preparation) pending, not scored failures before closure.

Stove2b64eda3 probe11158 closes **failure**,34decisions/1046steps; source is
before schema6. Same b136 source with only registered `lazy_planning_v1=False`
probe11159 succeeds **1decision/676steps**: move564,descend38,close15,turn59.
This flag ablation restores the original symmetric-wrist/contact-margin
search and native completion; it does not prove the full current stack fixed.
The first lazy source a1db4772 is probing as11163, scene tracking option omitted
because this historical source predates that feature. Its original CPU panel
520pass/2 stale-fixture failures is retained; fixture-only corrections21pass,
including rejection of unsupported header migration; production unchanged.

Saved measured stove plan diagnostic r3 identifies the exact new rejection as
**fixture_turn**, not ingress or closure. Both ±45deg checks compare the hand
to a stationary selected knob cloud; external scene counts are0. The report
is `.../2e3a401a/CPU_stove_saved_plan_contact_stages_r3.json`.
Two temporary support-fit hypotheses (trimmed local consensus and broad
connected-support regrouping) did not resolve the real failures; no such
changes were applied to production.

Current owned patch, staged tree90a2fec334ea80b64d56cd0eff369b3834b383a4,
resolves selected measured handles before accepting a merely reachable
stand-off, and predicts the clamped contact surface's motion during a wrist
turn. Other scene obstacles remain stationary; collision checks and native
task predicates are unchanged. New geometry tests include a static-obstacle
negative case and measured braking-start rebase. Focused52tests pass; exact
full panel runs under `/tmp/rd_selected_contact_staged_r3_20261022`, log
`/tmp/selected_contact_exact_r3_CPU_20261022.log`. No GPU result for this patch.
The preceding selected-wrist-only full panel664pass/1failure exposed a stale
withdrawal test that contradicted edd pending-grip semantics. The updated
empty/nonempty six-case test passes and never asserts held=True for pending.
Unverified point-SAM cache code/tests remain dirty and excluded from all
staged source archives. Generator v2 remains CPU-only/uncommitted.

Attached-body correction committed as **0514333776503c8af58d2ab656b8a3393c168a22**,
tree c61788dc6905818d783b4fedbc5beccadcee9d32; pushed to user-fork/harness-v5.
The origin upstream push returned403; the authorized user-fork push succeeded.
Exact archive /tmp/rd_attached_staged_20261022.tar.gz SHA256
1f672177a952f15fa9585b9129b9331743cd81e8bb1d2cb4fe05ffa0b6de7e40.
Whole requested CPU panel **761 passed**,317.83s; no dirty SAM-cache code included.
Raw saved support route CPU replay under the old owning source rejects both
container001 and bowl006; the exact corrected source passes46/9 samples.
Pinned replay evidence reports/attached_05143337_20261022/CPU_support_replay.json
(SHA256 f9cbebec9fb8d9b7041eafcc32c3fcbf3b0591055b601f629c5b4c82d43a92f7).

Jobs11176/11177 failed preflight before any controls: new plan retained old
baseline_source. Preserved originals; corrected r2 plan SHA256
c84c426cfc9d9904b0d7d5ad13ff533a1bbecdeb6ec5f41dcfeed02d6cf4e127,
manual same-launcher CPU preflight passed. Jobs **11178(container1),11179(bowl6)**
passed real physical startup; whole episodes still pending. Stove2 job11180
waits after11178. Node02 only/nice500; old historical daaa bowl11164 retained;
C2 curve11173 runs its own GPU; our maximum remains3 GPUs.

Closed D2 artifact audit confirms exactly **245** unavailable-variant trials,
**144** with missing public binding (8 cases,18 each across3 recovery tiers).
Explicit requested-variant matching exits before the pre-existing unbound
instruction/full-task fallback. CPU patch and regression checks are in progress,
not in05143337 or any physical source. All22 sampled-success/replay-failure
rows are indexed with trial seeds, initial hashes, selected parameters and
failed receipts; individual physical causes are not yet established.

The three exact05143337 probes are closed success: container1 2decisions/596steps,
bowl6 3/261, stove2 1/676; jobs11178/11179/11180 completed0:0.
Bowl still has a zero-control lower rejection before its successful release;
probe task success does not certify every primitive. Full fresh bounded30
(no pilots24/25) submitted **11181**,3shards,throttle2 while historical11164
uses a GPU. Same exact archive and r2 plan/common starts; no source edits
were copied into its execution snapshot. C2 runs11173; totalC3<=3.

D2 spatial_task_t1_s40 independent replay controls112 reproduced saved endpoint
with initial/final max residual **0.0**. Native done before forward=True;
a zero-control forward changes it=False, and old endpoint restoration=False.
This is a native derived contact/kinematics phase omission from integration
state, not an extra failed VLA retry. New native-buffer capture/copy and
unbound-call fallback pass44focused CPU checks; their exact staged snapshot
is being privately replayed. Not deployed to11181 or rescored historical D2.

Continuation checkpoint, 2026-10-22:

- Exact strict N1 tree7bfd88d4 (139431e9 object-chain removal on05143337)
  closes20/30 versus baseline25/30; all30 complete initial hashes match.
  Reports: `reports/object_contact_ablation_20261022/`; job11193 completed0:0.
- Bowl s5 good3d3edbb6 succeeds4decisions/745steps; first-round03552c03
  fails8/23 from the same complete initial state. Removing only the ordinary
  move-to future ingress veto (actual move/descend screens retained) restores
  s5 success. Standoff-only tree3c6bc6bf, CPU691pass, job11204 closes all four
  probes: idx15/1/6/2 = success4/745,2/596,3/261,1/676.
- Container s6 good99d90ae8 succeeds2/600; daaa1730 fails8/331, same complete
  initial. CPU replay of job11208's public input reproduces current rejection
  to1e-12m. A second lift screen narrows the already attached instance and
  retains a bottle pixel as a stationary obstacle. Reusing the cached complete
  attachment passes the same route, without changing collision margins.
- Source fix36dcaca6 and prefix compact-blocker cache fix6178f265 are pushed
  to user-fork/harness-v5. Strict execution tree2eb42379 excludes native-buffer
  transport and dirty SAM caches. Archive SHA256
  a2cd6f44a8833a33e846eb0bac2e9e501219972f18888839487b99359aacbfab.
  Exact CPU684pass plus startup/exit15pass. Test launcher imports env_server
  before tests that import MuJoCo; first unordered collection error retained.
- Job11211 uses this tree for idx19,15,1,6,2. Container19 already succeeds
  2decisions/600steps. Array11212 waits afterok11211, and additionally verifies
  all five closed physical results/source IDs before executing the full30.
  Throttle2 leaves one slot for bisection; no held jobs released.
- Stove s7 edge99d90ae8 success2/733 versus daaa failure10/385, job11209.
  Current and99d first665controls+public proprioception have identical SHA
  1a5b6314b02bf95a9c9ba50680cbd5274813873a405ebb58420fe079dfafd6f5.
  Old stack refreshes capture5 after zero-step wrist rejection and succeeds;
  current keeps capture4/1, marks all turns colliding, then reopens. Do not
  change this yet: if full30 remains below target, test removal separately.
- Historical daaa bowl s5 job11198_1 cancelled after42partial decisions/
  4692executed ticks, no closed score. Bisection job11213_0 probes object_task
  idx29 at b1365785 between good6a2d6bb8 and bad99d90ae8.
- D2 audit/code evidence is complete in
  `reports/attached_05143337_20261022/D2_THREE_ISSUES.md`. New D2/90-state/
  perturbation physical batches remain after N1 qualification. Shared
  coordination received `reports/attached_reuse_20261022/COORDINATION_NOTICE.md`.
