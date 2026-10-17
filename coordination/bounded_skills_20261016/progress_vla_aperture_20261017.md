# Calibrated thin-rim VLA handoff, 2026-10-17

Development code/simulation only. No model training or protected-job changes.

Job7716 provides a concrete missed handoff: the selected pick/bowl call used
18 pi0.5 blocks and 91 controls, ending in native task success. Public object
centre rose 61–96 mm at intermediate checks, but the held aperture was only
4.58 mm; the hard-coded >5 mm condition prevented a measured pick stop. The
native task success remains distinct from pick success; the original result
and private pick label (false after task placement) are retained.

The existing original-task empty-jaw calibration is reused, not re-estimated
from this pick. Runtime calibration file on5880:
`results/harness_v5/gripper513_original_opening_calibration_20261005/runtime_calibration.json`,
SHA256 `d4d977a5e5c23a23d80983ab34a4958373c6103035c2156ced24038204e4ca1c`.
Measured empty-closed upper plus tolerance is 0.00270244455896318 m. Source
and 540 robot-sensor samples are documented in
`coordination/gripper513_original_calibration_20261005.md`. This calibration
is robot proprioception/static geometry, not a task or grasp qualification.

Both bounded lift and call_vla use the registered aperture range when supplied.
Aperture alone never proves a grasp: lift still needs >=3 cm measured rise
and object/EEF coupling. VLA pick additionally needs two raised observations
with >=5 mm measured hand motion and <=15 mm relative motion. A stationary
pair cannot establish coupling; a previously established hold can remain
valid at the handoff rest pose. Missing current observations clear the window.

The feasibility and same-snapshot fork runners now actually consume their
pinned base configuration. Previously the launcher checked its existence,
but the probe ignored it unless --config was supplied; this silently omitted
registered sensor calibration. Explicit historical --config stays separate.
No schema/contract field changes or freely generated VLA prompts are added.

Validation: 52 focused CPU tests passed (bounded_skills, probe resilience,
bounded_vla); focused Ruff and diff checks pass. New regressions exercise
4.58mm moving held objects, measured empty/open jaws, stationary lifted
observations, retained post-handoff hold, and base-calibration propagation.
These are CPU checks; actual non-native VLA handoff and updated category
performance remain pending simulation.
