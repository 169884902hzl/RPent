# Stove off-endpoint false-positive diagnosis

Explicit source: job3643, original `libero_goal` task7/init0, `stove_turn_off_libero_goal_t7_s0_r0_vla_subtask160`. Its original receipt and all raw results remain unchanged.

The public packet measured 1,865 red surface pixels before the action and zero afterwards. All 28 old red-coil anchors remained visible at the same depth. Those facts establish a dark coil, not a closed control endpoint. Diagnostic-only joint labels changed from 2.100436 to 0.497362; the requested official `turnoff` predicate remained false. The old verifier nevertheless returned true. The correct label was independently queried for `turnoff`; this is a real false positive rather than an incorrectly queried setup predicate.

`measured_stove_rgbd/2-dev` retains visible positive red-coil evidence for on, and all existing current-depth/occlusion checks. When known coil support is visibly dark, it records `observed_coil_state=dark` and returns unmeasured with reason `dark_coils_do_not_measure_control_off_endpoint`. Thresholds were not relaxed. It does not claim successful off, or certify on without an independent confirmation batch. The exact original public evidence now yields null rather than true; the private joint fields are diagnostic labels only and are not consumed by the verifier.

The next measurable signal is the control handle itself. In this original main-view capture the control lies about 10 cm outside the SAM stove-shell bounds. Capture00 shows a complete elongated handle. Capture01/02 show the robot gripper over it; the coil remains fully visible while the control does not. A diagnostic-only black/depth proposal from public stove bounds gives a single complete cloud of 1,298 pixels and PCA elongation 3.35 initially, then multiple contaminated components with largest-component elongations 1.35/1.83. This proposal is not a semantic knob segmentation, endpoint detector or runtime change. Its geometry alone is insufficient to verify the endpoint.

Required next original-task measurement experiment:

- Original Goal task7, init0–9, development only. Fixed sequence: initial view, turn_on, turn_off; keep unsuccessful and partially rotated controls.
- Before every endpoint capture, release and retreat so the controller is unobstructed. Independently query SAM for the stove control/handle in main and wrist views; do not equate the stove-shell mask with the control mask.
- Save both RGB images, world point clouds, camera intrinsics/extrinsics, exact SAM masks and confidence, current control clouds, fitted axes/bounds and quality diagnostics, and current coil packets. Mark missing or occluded control measurements as unmeasured; cached coil support does not establish current control visibility.
- Store requested-mode predicates, joint qpos and native success only in separate diagnostic labels. Use those labels to evaluate the measured controller endpoint and both directions of error, never as runtime measurements.
- Validate complete off, complete on and naturally partial rotations. Only after observing an independent off endpoint should an off verifier accept it; no off template or coordinate is fabricated from simulation.

`report.json` records all nine explicitly downloaded RGB-D/metadata SHA identities, camera transforms, public packet and original receipt identity, baseline/current module hashes, and the diagnostic-only component measurements. CPU checks: 19 focused tests pass, including the exact original false-positive regression. No Slurm job was submitted and no physics qualification was claimed.

```bash
PYTHONPATH=. .venv/bin/python results/harness_v5/stove518_endpoint_FP_original_CPU_20261005/preparation/analyze_endpoint.py
.venv/bin/python -m pytest tests/unit_tests/robots/libero/test_v5_stove_measurement.py -q
```
