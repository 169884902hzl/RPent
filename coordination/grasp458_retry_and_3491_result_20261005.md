# Codex3: sustained-truth smoke closed; resource-race repair

**3491 COMPLETED0:0**,29m17s,48/48 closed paired first-grasp records,
zero initial-state mismatches>1mm and zero execution errors. Output
`results/harness_v5/grasp456_sustained_truth_20261005/smoke_job3491/`.
Original report SHA256
`d366d34a51ba2593e017e1faba6b91051d6c1e45220311158ce788094ffa2d7e`.
Private sustained truth30/48 across eight diagnostic conditions; this pooled
number is not a single-method qualification rate. Visual confusionTP28/TN17/
FP1/FN2; agreement45/48=93.75%,FP1/18 actual negatives,FN2/30 actual positives.
Each condition has only one trial/class;100/class and95% success remain
**uncompleted**. Do not treat nominal smoke Wilson intervals as qualification.

| Condition | True sustained holds /6 |
|---|---:|
| current direct |5|
| current above |5|
| current yaw90 |2|
| current restage |3|
| overhead short80 |5|
| reset/full80 |4|
| overhead short160 |3|
| reset/full160 |3|

With failure_reason correctly read,18 physical failures classify as15 no target
lift/hold,1 broken continuous hold,1 lifted without finger support,1 waypoint
not reached during trial lift. Two visual false negatives are a4.9mm bowl rim
and a visibly missing held moka pot;one visually accepted bowl loses contact
during the0.5s hold. No criterion was relaxed.

**3516** was submitted with the registered24-case stop/aperture smoke.
Actual `sbatch --parsable --dependency=afterok:3491 runtime_launchers/run_v5_grasp458_stop_aperture.sbatch`.
By then3491 and resource helper3493 had already completed;holding3493 returned
already finished, and3436 had started a second shard.3516 was therefore
stopped within44s to correct the transient three-GPU overlap. Its startup log
and output remain at `results/slurm-3516.log` and
`results/harness_v5/grasp458_stop_aperture_20261005/smoke_job3516/`.
This is an artificially interrupted startup, not a grasp/model failure;
closed-record count is checked separately. No old episode was altered.

New pre-submit reservation: same1GPU/8CPU/90GB/2h/nice1000/no binding,
now wait for3436_4 to free one of the two owned GPUs.3436 pending throttle
is1,3436_4/5 remain running unchanged. Actual retry command:
`sbatch --parsable --dependency=afterany:3436_4 runtime_launchers/run_v5_grasp458_stop_aperture.sbatch`.
New output `results/harness_v5/grasp458_stop_aperture_20261005/smoke_job<newid>/`.
Same source4571752/archive2e9fe18a4603569a85967b8eb8bb8b707b674f2838ab33438a2a1b85dd7829c5,
same24-case manifest643c3e90f8bcdc8b983c006a5635c35e58897410fb9f0ef56d7b2a3d9cbfc21b.
After its actual ID is known, submit one0GPU resource-restoration helper,
afterany:newprobe,using the exact unchanged helperSHA
`2c5bf9fe77cf042551deb159c3795bace8d7bbd9fb86697607265c04db40513c`.
3493 already ran and will not be reused as a pending dependency. Assigned
IDs will be recorded immediately. No A3/A4 qualification rerun or freeze.

Actual retry **3520** submitted once with the retry command above. Output
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp458_stop_aperture_20261005/smoke_job3520/`.
Actual CPU restoration **3521** submitted once:
`sbatch --parsable --dependency=afterany:3520 runtime_launchers/run_v5_grasp454_restore_concurrency.sbatch`.
Output `/public/home/sunyihan/rpent_libero_eval/results/slurm-3521.log`.
Both IDs were immediately appended to shared COORDINATION; the task watcher
includes interrupted3516 and retry3520. There are no duplicate live probes.

Corrected-classifier sidecar (original3491 report retained):
`results/harness_v5/grasp458_stop_aperture_20261005/baseline3491_CPU/report.json`,
SHA256 `2809ee1b9756358deec1195ff3fa1a17f2e0c3b7b93c09178cae0d593610e07a`.
Additional explicit-ledger process evidence:
`baseline3491_CPU/process_failure_evidence.json`, SHA256
`2d36831cbf595278b2773996481ae42791bb4a04fd75066078669b457c3c7071`.
Of18 final sustained-hold failures,6 had earlier chunk-end target/finger
contact plus body-origin rise;12 had no such sampled observation. These
chunk proxies never replace collision-bottom clearance or continuous hold
truth. They support testing an earlier public-proprioception contact stop
instead of simply increasing the chunk budget. The cancelled3516 ledger has
**0 closed records**, so it contributes no grasp attempt or score.

The full100/class launcher is prepared in commitc7fe608 but **not submitted**.
It will require a complete24-case probe with no execution/runtime errors and
known sustained truth before allowing the2400-trial four-condition cohort.
This is an instrument readiness check, not a success-threshold relaxation.
