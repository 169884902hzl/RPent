# Codex3: completed stop/aperture smoke and next root-cause probes

**3520 COMPLETED0:0**,12m35s,24/24 records,zero execution errors and zero
initial-reference mismatches>1mm. Private sustained success14/24 across four
conditions;visualTP14/TN9/FP1/FN0,agreement23/24=95.83%,FP1/10 negatives,FN0/14
positives. Each condition/class still has only one trial, so this is **not**
the100/class or95% grasp qualification. No family/condition is admitted.
Output `results/harness_v5/grasp458_stop_aperture_20261005/smoke_job3520/`;
report SHA256 `c4ca69a5fa83629f82451fce25c656af24e1eaaf001eaaeff2ed0faf6003282b`.

| Condition | True sustained /6 |
|---|---:|
| current thin80 |4|
| overhead thin160 |4|
| overhead RPent-stop thin160 |3|
| reset/full RPent-stop thin160 |3|

Ten final failures:8 no final target lift/hold,1 broken continuous hold,1 finger
contact without clearance. Frypan failed4/4;the target-first ambiguity remains
in the original two-object box instruction. An overhead wine-bottle approach
is measured atz1.2576m and fails while reset/full succeeds. RPent's public pick
success is not grasp truth:3cm visual lift and the private0.5s truth still
reject empty or unstable picks. The remaining visual false positive is the
moka overhead/public-stop trial. Its original receipt and hold samples stay.

New independent source:
`/public/home/sunyihan/rpent_libero_eval/source_v5_grasp459_bound_safe_retry1_20261005/`,
commit `115ba66`,archive SHA256
`c024d415ac8e9eb4492d2c2cd5ee781a986c20f525a644416d43f586185ddc93`.
Three conditions:reset pose + selected measured category first + original full
instruction;measured top+10cm safe transit/descent + short prompt;the identical
10cm arm with ordinary-English `frying pan` instead of `frypan` for the contact
policy. Alias does not change state/category names. Target binding and lexical
fixes do not count as additional physical methods. All use public RPent pick
stop,optional2mm aperture,and unchanged3cm/0.5s truth95/90/95 gates.
No simulator coordinates or BDDL goal are used to choose approach/prompt.
Defaults remain unchanged;no frozen behavior or new training admission.

Preparation `results/harness_v5/grasp459_bound_safe_retry1_20261005/preparation/`:
18-case smoke SHA256
`243c6d3a92d2eb4409a903321f744b8833dd8f2c7745c373a4a848070e91640f`;
1800-case100/class/condition full registry SHA256
`9dca2edd661ccba0d6e69efb595c8951ba9eccb16c74584e48e1007adfb175d0`.
Earlier459 preparation is unused;no GPU job ever launched from it.
150 focused checks passed;new10cm physical path and target-first prompt still
need this real probe. Full100/class trials remain unexecuted.

Resource correction:3521 already completed and restored3436 throttle2 before
the hold arrived. To prioritize the new sustained-truth requirement,stop only
obsolete50/class diagnostic3436_6 and pending3436_7–23;retain3436_5 running,
all completed episodes,logs and immutable source449. Mark the interrupted
3436_6 current unclosed episode as artificially interrupted development,
not training and not a measured grasp failure. Cancel never-started3448,
whose afterok full-old-array dependency becomes invalid. The old2400-trial
diagnostic stays explicitly incomplete,not silently treated as completed.

Pre-submit next probe1GPU/8CPU/90GB/2h/nice1000/no node binding,afterok3520
(already completed). Actual planned command:
`sbatch --parsable --dependency=afterok:3520 runtime_launchers/run_v5_grasp459_bound_safe.sbatch`.
Output `results/harness_v5/grasp459_bound_safe_retry1_20261005/smoke_job<newid>/`.
Retained3436_5 plus new probe stay<=2GPUs. Assigned ID will be appended
immediately. No new restoration job or old diagnostic re-submission.
Formal100/class launchers are prepared;following the failure-first rule,the
next full condition is selected only after this18-case root-cause probe.
No A3/A4 qualification rerun or behavior freeze has been started.

First submission returned `Job dependency problem`, **no job ID allocated**.
3520 remains COMPLETED0:0 in accounting;its24-case immutable report passed
the completion/error/hash check. The live scheduler no longer accepts3520
as an afterok reference. Launcher commit69296a1 now enforces that same
completed prerequisite through the pinned reportSHA before any GPU probe.
Launcher SHA256 `7474e77d1d7cf9e0de13fc23b9ce2bf4f70fef67a434e6fbe06332261d0e7245`;
execution source remains immutable115ba66/archivec024d415ac8e9eb4492d2c2cd5ee781a986c20f525a644416d43f586185ddc93.
Actual retry command is `sbatch --parsable runtime_launchers/run_v5_grasp459_bound_safe.sbatch`.
This references an already completed prerequisite,not an unfulfilled edge.
The metadata failure is not a grasp failure or a model result.

Resource cancellations executed.3436_6 has13 closed records retained;
interruption sidecarSHA256
`8eb1073e042a200c75199a1ada78e152f4d63eda99a67251f316e81c6548cd49`.
Only its current unclosed episode is artificially interrupted/not training.
3436_5 continues;old cancelled pending slices and3448 were never restarted.

Actual next probe **3545** submitted once with the retry command above.
Output `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp459_bound_safe_retry1_20261005/smoke_job3545/`.
18cases,three conditions,six classes,1GPU/no node binding. Actual ID,command,
source/launcher/manifest hashes were immediately appended to shared
COORDINATION and added to the job watcher. SchedulerMinJobAge=300sec confirms
why the completed3520 job ID could no longer be used as an afterok edge.
