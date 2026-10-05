# Codex3: stable grasp caller correction before physical execution

3561 was PENDING(Dependency),0 elapsed and0 physical trials;cancelled only
this new probe after discovering its two-frame result would be overwritten
by V5Executor._execute's final single-frame check. Registration/logs/source
retained. This is a pre-execution development correction,not a grasp failure.
3550 and3554 remain unchanged and continue.

Corrected caller uses explicit internal `final_grasp_measurement` evidence:
do not repeat the lift,do not refresh away the successful wrist measurement,
and retain both positive and negative two-frame results. The default contact
path has no marker and retains its existing behavior. Rendering fields are
unchanged;experimental receipt semantics are still not frozen or admitted.
156 binding/runtime/truth/state tests passed,including both caller outcomes.
20Hz controller default was checked in the installed robosuite source;prior
real diagnostic samples advance0.05s/control step. No private truth enters
the helper's action or success decision.

Pre-submit independent snapshot:
`source_v5_grasp463_final_measure_20261005`,commit3bbe36c,
archive SHA256 `408cb129bba62ba9377eff0426b37f31dd2ad6382d96098c8f5cd23500f402f0`.
12-case smoke manifest SHA256
`258d6aaf71cefb96bbe6abaae7f8904e5e3ab312b4ee3fc61d15c44f735eca49`;
full1200 prepared but not submitted,SHA256
`768b1e0c80d7d9711aa73fc7e5ccd5754b00a20f9cee47f7fba9dc2060d18eae`.
Launcher SHA256 `768d5043ee8c7807e14c3d9bb11752cb992fae5f3c5bc95404ddc208a1730448`.
Planned command,only after this receipt is pushed and shared COORD appended:
`sbatch --parsable --dependency=afterany:3550 runtime_launchers/run_v5_grasp463_final_measure.sbatch`.
Assigned ID not yet available. Output
`results/harness_v5/grasp463_final_measure_20261005/smoke_job<ID>/`.
1GPU/8CPU/90GB,nice1000,no node bindings,wait for the existing array to
preserve the two-GPU limit.12 original-task smoke trials only;all thresholds,
training exclusions and five-distinct-method accounting unchanged.
