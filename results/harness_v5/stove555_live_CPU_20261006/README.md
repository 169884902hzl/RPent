# SOURCE555 / job4210 public control measurement analysis

Job4210 completed the explicit ten original Goal7 initial states. It produced
all 80 scheduled capture packets and 160 camera views. All 20 contact calls
executed 160 five-action chunks (800 actions each); none recorded an
execution error. The eleven source hashes match the registered sampling manifest.
All four CPU preflights checked the ten official initial-state hashes.

| Public measurement coverage | Main view | Wrist view |
| --- | ---: | ---: |
| Saved calibrated views | 80/80 | 80/80 |
| Accepted current control pose | 0/80 | 4/80 |
| Pivot query with any raw instance | 8/80 | 0/80 |
| Tip query with any raw instance | 0/80 | 0/80 |
| Coarse stove query with any raw instance | 77/80 | 4/80 |
| Front-edge query with any raw instance | 0/80 | 0/80 |
| Directed lever / fixed reference / signed angle | 0/80 | 0/80 |

Both views have the same capture step in 80/80 packets. No packet measures a
control in both views. Every view's endpoint remains `unmeasured`. The four
accepted wrist control poses are all post-recovery off-phase views, from
original init3/5/7/8. These are extraction/geometry coverage figures, not
ground-truth semantic recall or qualified skill success rates.

The existing prompts remain `stove knob`, `stove switch handle`,
`stove switch pivot`, `stove switch lever tip`, `stove`, and
`front edge of the stove`. Across both cameras the two control queries returned
eleven raw instances: four accepted contact geometries and seven rejected as
not adjacent to the measured stove. Main-view pivot instances have no bound
control; they must not be treated as usable pivot measurements. Tip and
front-edge queries returned no instances at all.

`full_views_montage.png` and `control_crop_montage_context50.png` show six explicit
on/off capture pairs (t7/init0 and init5), selected without reading private qpos.
The green box is the same-capture coarse stove SAM bbox, or its public measured
AABB projected into the wrist view and intersected with current depth support.
Red boxes show existing control-query masks. Scores, bboxes, geometry and exact
rejection reasons are in `public_montage_report_context50.json`; all source RGB,
world and calibration references and hashes are retained there.

The images show why a coarse-body-only crop is insufficient: the black control
part sits outside the silver body mask. A 25% context crop retains only 59.4% of
the accepted init5 wrist control mask. The fixed 50% context crop retains 100%.
The exact pixel counts and the original mask SHA are in `control_crop_coverage.json`. The
main body mask is about 232–234 × 143–145 pixels in the 1024 image, with stove
scores 0.637–0.801 in the illustrated frames. The init5 wrist control query
returns a nearby candidate at score 0.359 (accepted contact geometry) and a
distant candidate at 0.281 (rejected with measured gap 0.154 m). The montage also
shows occlusion/truncation in some wrist captures; enlarging a crop cannot
restore geometry that the camera never saw.

The evidence supports one bounded crop-versus-full-frame smoke with the same
existing knob/handle prompts, same score and geometry rules, and a fixed 50%
coarse-fixture context. It does not support blindly adding more prompts or
fabricating pivot/tip direction. Crop SAM inference has not been run. The 100-cell
near-zero driver is software-ready, but its public directed-feature measurement
prerequisite is not met and no 100-cell job was submitted.

`crop_mapping.py` is an independent CPU helper; it does not modify runtime or
stove endpoint semantics. It rescales the crop RGB and records the pixel-centre
transform, corresponding cropped intrinsic matrix and unchanged camera-to-world
extrinsic. A returned crop mask is resized with nearest-neighbour sampling into
the original ROI, inserted into a full-frame mask, and used to index the original
saved world map. No depth interpolation, simulator coordinate or new point is
introduced. In all twelve illustrated real frames an all-foreground crop mask
selected exactly the original ROI's finite nonzero XYZ points. A separate CPU
check verifies a partial mask and the intrinsic/pixel-transform identity.

Reproduce after retrieving only references explicitly listed by
`selected_public_views_remote.json`:

```bash
PYTHONPATH=/home/agilex/cobot_magic/rpent_libero_eval \
  /home/agilex/cobot_magic/rpent_libero_eval/.venv/bin/python \
  /home/agilex/cobot_magic/rpent_libero_eval/results/harness_v5/stove555_live_CPU_20261006/render_public_montage.py

PYTHONPATH=/home/agilex/cobot_magic/rpent_libero_eval/results/harness_v5/stove555_live_CPU_20261006 \
  /home/agilex/cobot_magic/rpent_libero_eval/.venv/bin/python -m pytest -q \
  /home/agilex/cobot_magic/rpent_libero_eval/results/harness_v5/stove555_live_CPU_20261006/test_crop_mapping.py
```

The test passed (1 check). Its first invocation lacked the explicit helper
PYTHONPATH and failed to import; the corrected invocation above passed. The
analysis never opens private label files, PRO files, sealed instructions or
manual test texts. It submits no GPU work and writes no COORDINATION entry.

## Offline full/crop SAM handoff

The paired GPU smoke is ready in `offline_crop_sam_manifest.json` (SHA256
`122de1d0048033c2334044f849e61738384f0c98970e801cfd80be74aa226069`). It
uses the twelve saved public views listed explicitly in that manifest, the two
existing knob/handle queries, score threshold 0.2 and SOURCE555's unchanged
measured-control geometry. It performs 48 RPC calls: 12 views × 2 image
profiles × 2 queries. The full image uses the original PNG bytes; the crop has a
fixed 50% context around the current measured coarse fixture. It creates no
simulation and reads no private labels. Endpoints remain `unmeasured`.

The real entrypoint CPU preflight ran from remote `/tmp` and passed, as saved
in `offline_crop_preflight_from_tmp.json`: twelve RGB-D dimensions and original
XYZ selections checked, every explicit file SHA matched, and neither SAM nor
the simulator started. The comparison has not yet run, so it supplies no
evidence that crop SAM improves control measurement.

The root agent registers and submits the launcher; this CPU-analysis agent
does not submit it. The registered environment and actual command are:

```bash
export STOVE_CROP_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove555_live_CPU_20261006/offline_crop_sam_manifest.json
export STOVE_CROP_MANIFEST_SHA=122de1d0048033c2334044f849e61738384f0c98970e801cfd80be74aa226069
export STOVE_CROP_OUTPUT_ROOT=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove556_crop_SAM_original_20261006
sbatch --export=ALL /public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove555_live_CPU_20261006/run_offline_crop_sam.sbatch
```

The launcher requests one GPU for 30 minutes, uses the fixed SOURCE555 Python
path, starts and stops its own SAM daemon, and performs the same CPU preflight
before the actual run. It has no node binding. The output directory is
`$STOVE_CROP_OUTPUT_ROOT/crop_job$SLURM_JOB_ID`; its query ledger retains scores,
original-world point clouds, full-size masks, accepted geometry and rejection
reasons. Per-view/profile summaries count unique accepted control geometries.
The top-level query-coverage count is not a semantic-recall or endpoint metric.
