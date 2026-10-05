# Codex3: 3423 recovery and shared-harness regression

Accepted the 2026-10-05 01:30 PDT user instruction and Codex1's
`freeze_no_go_20261005.json`. Freeze and v5.1 training remain NO-GO.

3423 and its input are preserved. Its index generator emitted a literal
backslash-n at the end of JSON and supplied a string where the summarizer
requires a hashed manifest descriptor. The replacement uses `json.dumps`
with a real newline and explicit `{path, sha256}` inputs.

CPU replacement 3427 completed (0:0, 13 seconds):

- Command: `sbatch --parsable runtime_launchers/run_v5_freeze447_repaired_report.sbatch`.
- Directory: `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/freeze447_repaired_report_20261005/job3427/`.
- Files: `summary.json`, `report.json`, `paired_regressions.json`.
- Summarizer SHA256: `a2af6b8f3aad15f0db5b36dfa2e7b3567fcfdbf4ed35321e96c4c95771ef7eaa`.
- Original expert: official physical success 177/200; Spatial 49/50,
  Object 48/50, Goal 46/50, Long 34/50. Correct finish 0/200 is secondary:
  native success terminates the episode before an explicit finish.
- New development init41: A3 24/40, A4 24/40.
- Old development init40: A3 22/40, A4 18/40.
- Strict placement v5: TP61/FP4/TN19/FN33, 49 positive and 8 negative
  abstentions. Precision 61/65 = 0.938462; recall including abstentions
  61/143 = 0.426573. 13 of 187 attempts lack recomputable evidence.
  On precision/recall: 0.92/0.730159; in: 1/0.1875.

A4 relative to the previous 25/40 has nine regressions and two gains.
Regressions (all init40): 10_swap t0/t2, 10_task t2/t4, goal_swap t2/t3,
spatial_swap t4, spatial_task t0/t2. The paired artifact retains complete
receipts and sequences. Budget exhaustion is the termination, not a causal
diagnosis. Both groups have no memory card; cards do not explain this change.

Single-flag physical-prefix diagnostic 3428_0 and 3428_1 started on node01;
two GPUs total, no node binding. Nine regressions times eight flag settings,
72 prefixes, at most six recorded actions per prefix. Current, no safe
approach, legacy place, no cooldown, no held cache, no recovery, no view
retreat, no wrist hold. These are diagnostics, not live-model scores.

- Command: `sbatch --parsable runtime_launchers/run_v5_regression448_single_flag.sbatch`.
- Directory: `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/regression448_single_flag_prefix_20261005/job3428/`.
- Manifest SHA256: `08653a706c05a3dbe3b94f92b5dd907ca5f886c3cdc1b91d8ed5d8d591504136`.
- Replay script SHA256: `b9d005f471b4b7983f128b5788a959e38208ba4c84f778992c79d57851f61678`.
- Launcher SHA256: `88f24d61345e2e75194f5c2b3760c99ea3212404ef97a68aaba49853695ff921`.

The task-specific watcher records failed Slurm states to remote
COORDINATION within its 30-second polling interval. A record alone is not a
repair; the owner must inspect and handle the preserved error. The missed
3423 failure is acknowledged. No old run, budget, success rule, or development
split is changed.
