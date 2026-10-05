# Codex3 CPU milestone and stricter grasp requirement

Accepted the user's 2026-10-05 03:10 PDT revision: true sustained grasp
overall >=95%, every class >=90%, at least 100 first attempts per class;
runtime visual-verifier agreement >=95%, both false-positive and false-negative
directions reported, with per-class Wilson 95% intervals. The old 60% gate
is superseded. 3436's 50-per-class protocol is retained as diagnosis and
cannot qualify the new gate. No A3/A4 qualification rerun before grasp passes.

Completed CPU artifacts on the master:

- 3428 combined 72-prefix matrix and nine live A4 regressions:
  `results/harness_v5/regression448_single_flag_prefix_20261005/combined_cpu450/report.json`.
  SHA256 `a792a640aa8324580252bca4e7f8108bf25c9c8bae53cc7a8c59e7bd0b44726d`.
  Regressed live episodes contain 13 verified grasps / 189 attempts,
  107 contact chunk-budget stops, 55 approach misses, seven wrist misses,
  two waypoint misses and five execution interruptions. These are observed
  failures; contact noise prevents a unique causal-switch claim from prefixes.
- Twenty complete saved runtime requests re-rendered from recorded entities,
  receipts and recovery counters: 20/20 state UTF-8 byte identity and
  20/20 canonical JSON identity. Output `results/harness_v5/runtime20_450_CPU_20261005/`.
  Renderer SHA256 `f3e2215b6a972aa5053e5f574dfcb3ae08d76466a3c12e010e6f61bab68e6126`.
  These do not claim a new physics replay or raw HTTP transport-byte capture.
  Codex2 can inspect all 20 pairs in `requests.jsonl`. Execution-error cooldown
  only filters candidates; it adds no state row or field.
- Common pixel painter adopted in `robots/libero/v6_som.py::render_marks`:
  identical `v6_pixel_marks.py` SHA256
  `e57f251d310dbd67ff020f5425fa328b8daf34e17eadcf1c8f0762d588cabc72`.
  Fifty real saved LIBERO RGBs: 50/50 byte-identical PNGs, Pillow 12.3.0.
  Output `results/harness_v5/shared_pixels450_CPU_20261005/report.json`,
  SHA256 `664f67ce31e01d3900641c754f7f69a9a70f729b2512efbdafa416f41fc5347a`.
  Projection, SAM-mask/depth support, sim-truth rejection and omission semantics
  are preserved. No behavior freeze or new physical state follows from this.

3436 runs unchanged immutable source, with 3448 CPU report afterok:3436.
3448 launcher SHA256 `58b9320c38106c4246754348a213c2a6a549acefeeb65a91be24e56bad908117`.

Existing image prefix 3379 was freshly hash-checked, not regenerated:
manifest SHA256 `76f023182455d7596e1c5421205534399e29ed7b3ccdad53e7701fab47fd9647`;
train SHA256 `a81da8d68399ce102bc7cccf7a58dd062e323a11e7904d23e9dfdfbfc62c54b9`.
4,545 rows = 3,274 action + 1,271 auxiliary; 32 original tasks, 43 task/init
identities, 125 physically labeled action states; 930 registered rewrites.
All retained rows have two views; input-row coverage was 68.70%.
Fifty-image SAM overlap report: 206/227 marks >=0.5 IoU (90.75%);
all-marks-pass image fraction 66%, preserved and not conflated with mark rate.
682 wrong-instruction rows (15.01%), labels/candidates/images unchanged;
text-token P95 2161, max2354. Vision-token preflight and new behavior re-render
remain pending. Two failure-reason positive categories remain empty.
This prefix has full_training_admission=false and creates no independent
states through rewrites/images. It cannot substitute for the requested expansion.
