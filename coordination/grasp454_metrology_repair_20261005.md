# Codex3: grasp metrology repair and pending GPU comparison

Accepted the 10/05 03:10 PDT standard: at least 100 first grasps per class,
true sustained success >=95% overall and >=90% in every class, visual
verifier agreement >=95%, both error directions and per-class Wilson 95% CI.
Budget variants do not count as five distinct methods. No lowered threshold.

CPU job3468 failed before policy execution because OffScreenRenderEnv forces
a GL renderer and OSMesaCreateContextExt is unavailable in this environment.
CPU job3469 then found an instrument defect: deployed robosuite stores the
gripper as a dictionary. The private contact reader now gathers finger geoms
from the dictionary's components. Old source451 and both failures remain;
they are infrastructure/instrument records, not failed policy grasps.

Repair source: `/public/home/sunyihan/rpent_libero_eval/source_v5_grasp454_truth_20261005/`,
commit `5b41e38`, archive SHA256
`905aae638b94b17ac9a4be2d9f65e1360d92e0b621bb2aea001b4c16f42e4abc`.
Nine focused contact-truth and branch tests passed. The real CPU controls
use ControlEnv with no renderer and the same private metrology; worker RPC
and actual grasp behavior remain to be checked by the GPU probe.

Job3470 completed0:0 in23 seconds. All six original-task unheld controls
passed, each with11 samples over0.5 seconds. Report:
`results/harness_v5/grasp453_metrology_CPU_20261005/job3470/report.json`, SHA256
`b615820c65b1947f64b2c3448699c07a4888c8847c81103374cb896035b6356f`.
Actual CPU command:
`sbatch --parsable runtime_launchers/run_v5_grasp453_metrology_cpu.sbatch`.

The explicit completed3436 parts0/1 provisional trajectory report covers
200/2400 planned trials. Direct/above bowl failures include11 transient
dual-contact/body-lift observations followed by visual-verifier failure.
Frypan failures generally never show this proxy. These are separate failure
boundaries, not sustained-truth success or visual FP/FN counts. Output:
`results/harness_v5/grasp452_partial_CPU_20261005/parts01_report.json`, SHA256
`5e90571aaea2c4d4fabb8910465e24971e09d9bdf793a92a1b35ad49467c3426`.

Pre-submit GPU reservation:1GPU/8CPU/90GB/2hours, no node binding. Replace
held, unexecuted3457 and its dependent CPU restoration3459 because their
source has the proven private-instrument bug. Preserve their cancellation
identities, with zero policy calls; leave active3436 episodes/source intact.
3436 pending concurrency stays1, so the repaired probe follows
`afterany:3436_3` and total Codex3 use stays <=2GPUs.

Planned actual command:
`sbatch --parsable --dependency=afterany:3436_3 runtime_launchers/run_v5_grasp454_truth_smoke.sbatch`.
Output `results/harness_v5/grasp454_sustained_truth_20261005/smoke_job<allocated_id>/`.
Uses the unchanged48-case manifest SHA256
`99d06df0d8c187db4d4f75df632d495cfd3bd80f282a58cd8c0e264de03ad1e3`.
The assigned job and afterany CPU concurrency-restoration IDs will follow.
No100/class full run, A3/A4 acceptance rerun or behavior freeze is admitted yet.

Repaired GPU probe **3471** was submitted once with that exact command.
Output `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp454_sustained_truth_20261005/smoke_job3471/`.
3457/3459 were cancelled before execution; no episode was interrupted.
Pre-register0GPU/1CPU/2GB restoration afterany:3471. Planned actual command:
`sbatch --parsable --dependency=afterany:3471 runtime_launchers/run_v5_grasp454_restore_concurrency.sbatch`.
Output `results/slurm-<allocated_restoration_id>.log`. This restores the
temporary3436 throttle after the repaired probe, with actual state verification.
