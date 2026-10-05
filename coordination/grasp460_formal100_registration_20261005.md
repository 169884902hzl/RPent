# Codex3: first100/class sustained-truth comparison

**3545 COMPLETED0:0**,8m33s,18/18 closed records,zero execution errors,
zero initial-reference mismatches>1mm. Output
`results/harness_v5/grasp459_bound_safe_retry1_20261005/smoke_job3545/`;
report SHA256 `7df7ec6de866517d9af40e0ba308754b42ec225582fc3b97a18aad6c5bd4c284`.

| Condition | True sustained /6 | Verifier agreement |
|---|---:|---:|
| reset/bound full160 |3/6|6/6|
| safe10cm/short160 |4/6|5/6|
| safe10cm/alias160 |6/6|5/6|

Across all18 mixed conditions:TP12/TN4/FP1/FN1,13 real successes,agreement
16/18=88.89%. Five physical failures classify as4 no final target lift/hold and
1 finger contact without full support clearance. Frypan short-prompt trial
visually rises5.03cm but fails true clearance;this is the remaining false
positive. Moka alias trial truly holds but is visually missed. Keep original
receipts/hold samples. Ordinary-English frying-pan condition succeeds once;
one trial cannot establish an alias causal effect. Other classes share the
exact same short text,so their differences are policy noise,not lexical gains.

The promising6/6 condition has pooled nominal Wilson95% interval
[0.6097,1.0]. Each class is still n=1. **No95%/90%/95% qualification or behavior
freeze.** Neither target-order repair nor budget/alias variation counts as an
additional physical method. Five genuinely distinct failed methods have not
been completed;no standard is lowered and no user stop threshold is claimed.

Pre-submit formal comparison:1800 registered first trials =3 conditions ×
6 classes ×100. Same task/init/category pairs,original tasks only. Moka/frypan
have50 distinct official initial states reset twice;report unique counts and
nominal Wilson scope. No PRO/Jev/102-human/sealed-test input;all diagnostic
trials excluded from training,including the original init10–39 subset.
Truth remains3cm collision-bottom clearance,no original support contact,
continuous finger support0.5s. Report class Wilson intervals and both FP/FN
directions;unknown/missing trials cannot become model failure counts.

Source `source_v5_grasp459_bound_safe_retry1_20261005`,commit115ba66,
archiveSHA `c024d415ac8e9eb4492d2c2cd5ee781a986c20f525a644416d43f586185ddc93`;
full manifestSHA `9dca2edd661ccba0d6e69efb595c8951ba9eccb16c74584e48e1007adfb175d0`.
External full launcher commitee269ee,SHA256
`5463a9ba4db5315cf917bcd09e7cd578c34e035c79356c7d4b659b7254fa3ad0`.
It hash-checks3545's completed18-case report and instrument readiness before
running. The predecessor's live Slurm ID may expire at300s;the fulfilled
prerequisite is retained as the immutable report,not bypassed.

3436_5 has exited the queue;verify accounting and no owned live GPU work
before submit. Old50/class source/closed records remain unchanged;old full
diagnostic is incomplete after documented cancellation. Formal array18shards,
throttle2,1GPU/8CPU/90GB each,4h/shard,nice1000,no node bindings.
Planned actual command:
`sbatch --parsable runtime_launchers/run_v5_grasp459_full.sbatch`.
Output `results/harness_v5/grasp459_bound_safe_retry1_20261005/full_job<arrayid>/part0..17/`.
Assigned ID will be recorded immediately. Then submit one0GPU CPUreport,
afterany:arrayid,using launcherSHA
`f38dd58a1556c2455ec170a6afe157d762ecc772f86f58d7c1df7664b121f061`.
Explicit18 ledger paths only;retain missing/incomplete shards/accounting and
partial qualification=false. No A3/A4 rerun or freeze before the grasp gates.

Actual formal array **3550** submitted once with the command above.
Output `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp459_bound_safe_retry1_20261005/full_job3550/part0..17/`.
3436_5 verified COMPLETED0:0,54m54s;all older owned GPU jobs are terminal.
Actual CPU summary **3554** submitted once:
`sbatch --parsable --dependency=afterany:3550 --export=ALL,GRASP_FORMAL_ARRAY_ID=3550 runtime_launchers/run_v5_grasp459_report.sbatch`.
Output `results/harness_v5/grasp459_bound_safe_retry1_20261005/report_job3554/`.
Both actual IDs/commands/paths/SHA were immediately appended to shared
COORDINATION.3550's18 shards and3554 are registered with the task watcher.
Status is submitted,**formal counts/results and qualification unfinished**.
