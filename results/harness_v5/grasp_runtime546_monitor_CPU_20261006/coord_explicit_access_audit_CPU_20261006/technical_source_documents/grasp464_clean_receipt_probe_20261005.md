# Codex3: keep probe control markers out of rendered receipts

Final caller check found the internal final-measurement marker would be copied
into the receipt JSON,which serialize() emits verbatim. Pop it before receipt
construction. The experimental verifier now preserves two-frame outcomes
without adding a public state/receipt field.156 relevant tests pass,including
asserting marker absence. No default-runtime behavior changed.

3563 remains unexecuted PENDING(Dependency). Cancel this probe only and retain
its registration/source;3561 already cancelled before execution. Neither has
physical records or a model score.3550's fixed source/1800-case cohort and3554
are untouched. This pre-execution format correction is kept separate.

Replacement pre-submit registration,after pushing this receipt and appending
the shared COORD:
`sbatch --parsable --dependency=afterany:3550 runtime_launchers/run_v5_grasp464_clean_receipt.sbatch`.
Job ID not assigned yet;1GPU/8CPU/90GB,nice1000,no binding. Wait for the whole
3550 array,so this task never exceeds two GPU.12 physical smoke trials only.
Output `results/harness_v5/grasp464_clean_receipt_20261005/smoke_job<ID>/`.
Source snapshot `source_v5_grasp464_clean_receipt_20261005`,commita95e29e;
archive SHA256 `0c30125a755af71ca1d2ccf3d12264a516ba7bcaf0fce4ae4105a062c7f4a5af`;
launcher SHA256 `1301a42418f7bfdd3368cd58406747568367987706a63813ec455674cc0c4b3e`.
Smoke manifest `258d6aaf71cefb96bbe6abaae7f8904e5e3ab312b4ee3fc61d15c44f735eca49`;
full1200 registry prepared only,SHA
`768b1e0c80d7d9711aa73fc7e5ccd5754b00a20f9cee47f7fba9dc2060d18eae`.
95% overall/90% per-class/95% verifier gates unchanged;100/class formal3550
still running;new smoke does not establish qualification. No five distinct
formal methods completed,no A3/A4 rerun,no behavior freeze,no training admission.

Codex1/2: experimental measured lower-extents/two-frame receipts are not a
frozen runtime change. If physically validated and adopted,the new receipt
semantics must be supplied for training rerender. Existing renderer131 and
running3550 artifacts are unchanged.

Actual replacement **3565** submitted once withafterany:3550,the registered
command and launcher above. Output
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp464_clean_receipt_20261005/smoke_job3565/`.
Pre-submit code/receipt pushed2010609;actual ID/command/path/SHA immediately
written to shared COORD.3563 CANCELLED before execution,zero elapsed;
3565 PENDING(Dependency),physical test unfinished.3550/3554 preserved.
