# Public payload-surface rotation repair, 2026-10-17

Simulation development only; training=false. Canonical contract remains
`SKILL_PACKAGE_SPEC.md` and `rpent/skill_package/schema.json`. No confirmation
state is admitted to training, and no c5/c6 job is modified.

## Evidence and change

At 2026-10-17 09:49 +08, jobs 7719/7720 had 21 completed physical results,
0 successes. These are incomplete original-development cohorts, not category
qualification or confirmation. The remaining not-yet-started continuations
were cancelled for diagnosis; one shard (7719_25) started during cancellation
and its partial artifacts remain. Existing completed and running artifacts
are retained under `results/bounded_skills/feasibility_20261017` on 5880.

In 7719_1 row 4, carry was rejected at its initial pose because a payload point
and a scene point were 1.177 mm apart. Both are in the agentview bowl mask,
but the depth-component cleanup omits that lower edge. The wrist view does
not independently see this edge (nearest current wrist sample is 8.72 mm
away); a mask alone therefore does not establish moving ownership.

The pre-lift capture, current clean dual-view surface and measured EEF motion
support a small grip rotation. A rigid ICP fit gives 0.03895 rad (2.23 deg),
maximum surface correction 4.75 mm, median fit residual 1.912 -> 0.449 mm.
The rejected scene point is 39.09 mm from the old stationary scene. This
supports grip compliance as the missing model term; simulator object poses
were not used.

`bounded_payload.py` now fits translation and rotation together, with maximum
surface displacement 15 mm and rotation 0.1 rad. The existing 4 mm surface
association and stationary-scene thresholds remain. Every point in the
predicted surface must respect the displacement bound; static neighbours
continue to win over moving matches. Large or weak fits supply no correction.

## CPU validation

- 86 focused bounded-skill pytest cases passed. Warnings: the local pytest
  installation lacks the timeout plugin; existing OmegaConf deprecations.
- Same saved capture, same boundary reconstruction: the old translation fit
  associates 0/24 rejected points; the rigid fit associates 24/24.
- Reports: `reports/payload_20261017/translation_surface_7719_1_CPU.json` and
  `reports/payload_20261017/rigid_surface_7719_1_CPU.json`; source artifact
  SHA256s are included. Replay does not repeat robot self filtering and makes
  no route-pass/task-success claim.
- New regressions cover a tilted moving edge, retained stationary neighbour,
  and rejection of a large grip rotation. Existing translation tests pass.
- Compile check, focused Ruff check and `git diff --check` pass.

## Physical next check

Run the exact launcher/snapshot to its first physical request, then complete
the same bowl state with oracle K=1 and K=4. Only after the route and task
results establish the effect should broader original-category trials resume.
Remaining categories must still be repaired and reported with Wilson
intervals, decisions/steps and phase counts. Historical expert 197/220 and
pi0.5 control 215/220 are separate controls, never bounded-oracle results.
