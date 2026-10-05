# Codex3 continuation: original-task grasps and paired regression evidence

Accepted the user's 2026-10-05 01:30 and 01:45 PDT instructions. All old
records remain. No SFT3 rerun, shared service change, training admission or
behavior freeze is authorized by the component checks below.

3434_0/1 completed with exit 0:0; the explicit 48-trial report is complete,
with no initial object reference mismatch over 1 mm. Smoke visual checks by
condition (six objects each): direct 5/6, above_10cm 4/6, yaw_90 2/6,
restage 5/6, high_short80 3/6, start_full80 4/6, high_short160 6/6,
start_full160 4/6. These are startup checks, not the 50-per-class acceptance.
Report SHA256: eedf5c54d70a074c995d0aaa034220ee0af05d5efca6455ae6e664a31ff735f9.

3436_0/1 are running, other shards remain dependent/queued. The fixed
source `source_v5_grasp449_20261005` is unchanged. No duplicate GPU job is
submitted. Full manifest registers 2,400 original-task first attempts and
eight paired conditions; visual and private diagnostic contact results are
reported separately. A single finger can support a handle/rim, so lack of
opposing-pad contact alone is not proof of a visual false positive.

Pre-submission CPU reservation: no GPU, two CPUs, 12 GB, 20-minute limit,
no node binding. One full-report job afterok:3436 reads exactly the 24
registered ledgers. Planned command:
`sbatch --parsable --dependency=afterok:3436 runtime_launchers/run_v5_grasp449_report.sbatch`.
Output: `results/harness_v5/grasp449_original_paired_20261005/report_job<allocated_job_id>/report.json`.
The job ID is assigned by sbatch and will be recorded immediately afterward.

Independent CPU work now: summarize all 72 completed 3428 prefixes with
the nine regressed episodes in the preserved 3427 paired artifact. This
does not change a score or establish a single causal flag: Pi0.5 noise was
not paired. Output: `results/harness_v5/regression448_single_flag_prefix_20261005/combined_cpu450/`.

The evaluation-only original recipe executor has eight passing targeted
tests. Its real RPent API outcome is inside `log.result`; the outer captured
environment has image bytes and simulator state and is not serialized into
the recipe receipt. Original commands and parameters are unchanged, errors
retain the same recipe step for recovery, and intermediate pi0_doubled
execution remains unverified rather than being confused with native done.
All 40 explicit raw memory indexes were examined: 38 have recipes; two have
none (object_swap t2, goal_swap t0), to be retained and disclosed in full
evaluations. Physical recipe smoke and A2-M/A4-M are not yet run. The former
stock vLLM service at node02:18373 is no longer live; no patched service is
substituted. These arms will use the same stock vLLM recipe after resource
reservation, not infer readiness from the old ready.json.

Freeze remains NO-GO: the complete paired grasp comparison, physical strict
placement validation, and full new41/old40 A3/A4 reruns are outstanding.
Image expansion, perturbation collection and model-driven DAgger remain
work in progress; this receipt makes no claim of new training rows.
