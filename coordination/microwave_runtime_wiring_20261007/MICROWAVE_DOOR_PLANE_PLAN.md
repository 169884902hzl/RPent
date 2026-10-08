# Microwave door-plane measurement plan

This is a development measurement plan. It does not use simulator joints,
solved predicates, or private masks for runtime control.

## Public inputs

1. Retreat the arm and capture at least two time-separated RGB-D frames for
   each phase (`before` and `after`), spanning at least 0.3 s.
2. Transform each depth cloud with the registered camera intrinsics and
   extrinsics into the world frame. Record camera identity, source step, and
   timestamp.
3. Query SAM deterministically with `door of the microwave`. Keep a door mask
   only when it has finite depth and is adjacent to the measured microwave
   shell. If the query is missing, use the current adjacent-panel geometry
   hint to request one additional SAM mask; do not reuse a stale mask.

## Plane fit and endpoint evidence

For every accepted mask, fit a vertical plane robustly to the current 3-D
points, reject non-planar residuals and points outside the shell-adjacent
bounding box, and retain the plane normal, centre, bounds, residual, point
count, mask id, and SHA-256 of the measured cloud. Compare the moving-door
plane with an independently measured shell-front plane. A frame is measured
only when both planes are present and stable across the two captures; otherwise
the receipt is `unmeasured` with the concrete missing-support reason.

For `open`, endpoint evidence is a stable door angle above the open threshold;
for `close`, it is below the close threshold. Require the same endpoint in two
successive public measurements and a direction-consistent change from the
before phase. Runtime stopping may be admitted only from this public temporal
evidence plus proprioceptive contact/withdrawal evidence. Simulator joints may
be used later as training labels for a separate temporal verifier, never as a
runtime feature or control signal.

## Identity and missing-data rule

Track the door between frames using current RGB-D mutual correspondences and
plane agreement. If correspondences or current depth support are absent, keep
the frame as a diagnostic record and return `unmeasured`; do not bridge the gap
with a previous mask or relax the plane threshold. The 4594 smoke found the
limitation: agentview moving planes 41/48, wrist 0/48, identity recovery 1/48,
and temporal stops 0.

## Work estimate

- Existing public geometry and receipt wiring: complete in the current source
  (`66e588fc892c15f5fddb3e047664fd0f05beb5c5`).
- Public temporal verifier data contract, sequence capture, and unit tests:
  0.5--1 engineer-day.
- Fit/identity validation on original microwave tasks (10 smoke episodes plus
  non-overlapping confirmation states), including error and missing-support
  breakdown: 1--2 engineer-days, depending on RGB-D coverage.
- Only after those pass, train/evaluate a small RGB-D + proprioception temporal
  verifier with simulator joint labels and run a held-out public-input check:
  1--2 engineer-days.

The current blocker is public current-depth support under the changing door
view, not a single threshold. The minimum credible runtime-stop milestone is
therefore approximately 2--4 engineer-days beyond the existing geometry
prototype.
