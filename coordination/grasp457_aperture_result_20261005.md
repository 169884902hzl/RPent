# Codex3: empty-gripper measurement completed; sustained-grasp diagnosis continues

Recovered the already submitted CPU job **3503**; it was not resubmitted.
Actual command:
`sbatch --parsable runtime_launchers/run_v5_grasp457_aperture_cpu.sbatch`.
Completed `0:0` in 24 seconds, 0 GPU, no node binding.

Output:
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp457_empty_aperture_CPU_20261005/job3503/report.json`.
Report SHA256:
`3c81c7d6dd14893891ca6109b9e11a1feec2029b031a57475e2e6845e6756553`.
Source snapshot `source_v5_grasp457_aperture_20261005`, commit `a10cc59`,
archive SHA256 `e10c06e86305ee39412ef7c113605134ee727c419ea3369b4bd40b6d1873aabd`.

Six original-scene empty-gripper controls passed. With the runtime's exact
float32 aperture conversion, the last ten closure samples range from about
0.9995 to 1.1927 mm. This is a proprioception control, not a policy success
rate or a grasp qualification. It supports testing a lower nonempty aperture
boundary without treating an empty closed gripper as holding an object.
Runtime defaults have not changed.

GPU probe **3491** remains running with real policy motion and the registered
3 cm clearance / 0.5 s continuous finger-support truth instrument. At the
current read, 35/48 records are closed, with no execution errors. At least one
bowl trial has true sustained grasp but visual false because its aperture is
4.9 mm, below the old 5 mm boundary. Another visually accepted bowl trial
loses finger contact during the hold. Both raw records remain intact; these
distinct causes must be fixed and measured separately. One trial per
condition/class cannot establish the user's 100-trial or 95% criteria.

**3436_4** continues immutable old diagnosis; pending throttle remains 1.
**3448** waits for that old array; **3493** waits for 3491 to restore resources.
Codex3 currently uses two GPUs. No node bindings, no A3/A4 qualification rerun,
no behavior freeze, and no full 100/class sustained-truth trial has run yet.
The 95% overall, 90% per class, 95% verifier agreement standards are retained.
