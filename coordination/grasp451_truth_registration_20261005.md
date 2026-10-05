# Codex3: sustained-grasp diagnostic registration before submission

The 2026-10-05 03:10 PDT standard is accepted. Original-task metrology will
measure collision geometry lifted at least 3cm above its settled initial
support level, without original support contacts, continuously supported by
the gripper's fingers during a 0.5-second stationary hold. Opposing-pad contact
is saved separately; single-finger handle/rim support is not automatically
called a failed grasp. The complete contact/clearance time series is retained.
Runtime measured verification is recorded before this private hold. Its false
positive and false negative counts/rates and agreement are reported separately.

Only the original-task private oracle offers the hold RPC; no PRO facade,
runtime state, candidate or planner receives simulator truth. This post-skill
metrology is outside the policy budget and no action is selected using it.
Old3436 uses its original source unchanged; it remains a 50-trial diagnostic.

Prepare an explicit 100-trial/class x8-condition registry (4,800 trials),
not a training package. Methods preserve the paired original task/init batch.
For the moka pot and frypan, the available unique visible reference is one
original task with50 official initial states. Register two separate reset
trials per state, disclose50 unique states separately; do not claim100 new
states. Other classes use100 distinct task/init identities when available.
Pi0.5 noise is not fixed across conditions; Wilson intervals are nominal
binomial intervals with repeated-state counts disclosed. No further independent
initial states are invented. Report failure classes before choosing the next
method; budget variants alone are not five genuinely different methods.

Pre-submit GPU reservation: one GPU/eight CPUs/90GB/two-hour maximum,
no node binding, nice1000. The first job validates this private metrology on
48 trials, not the100/class acceptance. It will follow afterany:3436_0.
3436 pending-array concurrency becomes1 while this job runs, without
interrupting current episodes or modifying its source, so Codex3 remains at
most2 GPUs. Restore3436's concurrency2 after this probe exits. No new full
100-trial run or A3/A4 acceptance run is released before reviewing failure
classes and the metrology output.

Actual planned command:
`sbatch --parsable --dependency=afterany:3436_0 runtime_launchers/run_v5_grasp451_truth_smoke.sbatch`.
Planned source: `/public/home/sunyihan/rpent_libero_eval/source_v5_grasp451_truth_20261005/`.
Output: `results/harness_v5/grasp451_sustained_truth_20261005/smoke_job<allocated_job_id>/`.
The ID and preparation/source hashes will be recorded after assignment.
Target remains true success >=95% overall, >=90% per class, and measured
verifier agreement >=95%, with at least100 first attempts/class. No freezing
or lowered threshold follows from this smoke. Existing3436/3448 are preserved.
