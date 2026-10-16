# Codex3 bounded skills progress — 2026-10-16

Source `84cf146`, pushed to `user-fork/harness-v5`. No training, no real robot, no c5/c6 changes or old held releases.

Canonical source `/home/agilex/cobot_magic/rpent_libero_eval`:

- `SKILL_PACKAGE_SPEC.md`: SHA256 `3092f22056221c69606462de9acb059dea2e0ffd45aac70ab5381a395a27360a`
- `rpent/skill_package/schema.json`: `647ea9f0846ba044111b703558cf5336c608ce31b93ca5b13fcd0a34802505e8`
- `contract.py`: `f2cce2e68b80e9f10c112e486929f2c08a324ea516f7104502c734cf8fcb5df5`
- `trajectory.py`: `ad28744d3facf151d7b8914eaabe07fe27efe58dc1b71b90be64ca224c355a58`
- Remote snapshot `/public/home/sunyihan/rpent_libero_eval/source_bounded_84cf146_20261016`, tar SHA `a6cd4000130c3f666e95fcae1b8b7f66da54adcd00c96179122af0dd4e122a32`.

Schema remains bounded-skills/1 with optional measured `relations` triples; unknown anchor IDs are rejected by the canonical validator. History is mandatory for call_vla and null for other skills; n=0 requires null rate/step estimate; n>0 requires a source manifest SHA. Codex2 must reload canonical bytes and update pinned source hashes, not carry old modules with new file hashes.

Shared trajectory now uses three quintic spans per original segment, with two internal knots to constrain p/v/a/jerk at both ends. Span junctions are C4; original waypoints/chunk-rest junctions C3 with zero jerk. `Trajectory.waypoint_times` identifies original waypoints; spans are not decisions. Thirty focused CPU checks passed. This is not a global minimum-jerk optimality claim. C3 physical comparison is job7520, pending results.

Earlier C2 motion: jobs7514 and7516–7519 cover 20 original initial states ×3 identical waypoint sequences ×4 methods. Raw results remain under results/bounded_skills/motion_20261016/job*. All jobs COMPLETED; full route completion is being independently recounted. Seed0 completed all 3 paths with new terminal errors <6.3mm; jerk RMS old 7.4–11.0m/s³, newK1 .62–.82, newK4 .32–.48. These are C2-only development results, not C3 evidence. Existing visual self-filter at 2mm missed six robot link7 edge pixels at 2.0–2.3mm; current 4mm self-surface band solved these seed0 routes without changing the 4mm scene collision clearance. No broad workspace carve.

7511 failed on simulator import order;7513 failed on unsupported executor kwargs. Both logs preserved and repaired.7515 is a true first-physical-request startup check,633 move_to simulation steps; not task success.7521 repeats with C3 and candidate-generation profiling.7522 tests actual call_vla through the real π0.5 component. Both currently pending physical evidence.

Remaining: full category feasibility, exact historical171 baseline, real VLA handoff measurements, development-only history statistics, snapshot oracle/VLA branch pairs, real asynchronous decision-service integration. Full-task VLA remains isolated comparison only; oracle upper-bound requests have call_vla disabled. Candidate goals and geometry are public RGB-D/proprioception; private task predicates are used only by the explicitly isolated oracle selector/scorer. No model policy success claimed.
