# Codex3 held-grasp instrument smoke submitted

3457 submitted once, oneGPU/no node binding, dependency afterany:3436_2.
Actual command:
`sbatch --parsable --dependency=afterany:3436_2 runtime_launchers/run_v5_grasp451_truth_smoke.sbatch`.

Output `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp451_sustained_truth_20261005/smoke_job3457/`.
Source `/public/home/sunyihan/rpent_libero_eval/source_v5_grasp451_truth_20261005/`,
commit ae50e30, archive SHA256
`14e31df7b1c7ac31d7de84eb988e05e348e5a5f4c84005776a97d333f76874bd`.
48-trial smoke manifest SHA256
`99d06df0d8c187db4d4f75df632d495cfd3bd80f282a58cd8c0e264de03ad1e3`;
100/class4800-trial registry SHA256
`2f1d50e50a8e4d39088b2e1c7e49def59c318e3706fff481280697908c2b4b21`.
100/class full run not submitted, pending physical metrology and failure review.

3436_0/1 completed0:0 while preparation ran.3436_2/3 were already active,
so the smoke dependency was changed from the preplanned3436_0 to3436_2
before submission. Pending3436 throttle1 is verified; running slices were
not interrupted. Total Codex3 GPUs stay <=2. Pre-register a0GPU/1CPU/2G,
five-minute CPU cleanup job afterany:3457 to restore3436 throttle2 and verify
the remaining array's state; output `results/slurm-<allocated_job_id>.log`.
Actual planned command:
`sbatch --parsable --dependency=afterany:3457 runtime_launchers/run_v5_grasp451_restore_concurrency.sbatch`.
That job ID will be recorded immediately after assignment.

Codex1/Codex2 renderer delivery (format131 family, not behavior-frozen):
`source_v5_grasp451_truth_20261005/robots/libero/v5_state.py::serialize`
and `::prepare_request`; interpreter
`/public/home/sunyihan/rpent_libero_eval/.venv/bin/python` (Python3.10).
State-source SHA256 `f3e2215b6a972aa5053e5f574dfcb3ae08d76466a3c12e010e6f61bab68e6126`.
These entries passed the20 saved-request byte comparison; this is not a
training re-render or behavior-freeze admission. Strict place6 and full
new41/old40 A3/A4 verification remain outstanding under the revised grasp gate.
