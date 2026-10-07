# 4311 public endpoint CPU continuation

No GPU job, physical trial or training row was added. The three binding failures
and seven footprint false negatives retain the original 4311 verdicts. This
analysis does not qualify a verifier or change strict6 thresholds.

The prior public geometry report remains at
`results/harness_v5/place4311_public_identity_CPU_20261007/report.json`, SHA256
`fb19d66f807226d28212212db3b8e1ec61dc25c8e2bd118bc5992b2f5584765c`.
It already resolved two thin horizontal drawer aliases in CPU prompt binding.
The remaining t25/init2 cabinet ambiguity lacks an independent current drawer
query. Existing cabinet-derived parts cannot prove that their cached semantic
parent was actually a drawer, so they were not removed.

New report on gpu5880:
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place4311_endpoint_public_CPU_20261008/report.json`
SHA256 `a9ad0a0c675bed101cf8fb7ef3da262d741cf17277d60139fa250838fc49ca49`.
CPU producer in the same directory `analyze_place4311_endpoint.py`, SHA256
`6e1f61cc0bf8d26f33e4e2621ea77b9cd6bed25eb887443d2129117cd85928c3`.
Its exact local invocation is:

```bash
python3 coordination/drawer_public_identity_hold_CPU_20261008/analyze_place4311_endpoint.py \
  --root /home/agilex/cobot_magic/rpent_libero_eval \
  --explicit-inputs /home/agilex/cobot_magic/rpent_libero_eval/coordination/drawer_public_identity_hold_CPU_20261008/place4311_endpoint_r2 \
  --output /home/agilex/cobot_magic/rpent_libero_eval/results/harness_v5/place4311_endpoint_public_CPU_20261008/r3
```

Inputs are explicit saved indexes and files, not filesystem enumeration. Six
step7 RGB/world/calibration files were downloaded for original LIBERO-90
t25/init4, plus four explicit public robot-state indexes for current-place
t10/init2 and t25/init0/1/2. Their remote backup is the report directory's
`explicit_inputs/`. The manifests retain the original remote path and exact
local path for the CPU invocation. Only robot proprioception is read from
these indexes; no simulation object coordinates or PRO files are read.

For t25/init4 vla_subtask, the saved bowl box is 11.06 times its pregrasp volume,
with upper_z=1.271484m. At the exact second frame, the main RGB-D world map has
4,299 points inside this box but its 98th-percentile z is only 1.177734m; only
four points are above 1.23m. The wrist map has zero points inside the saved box,
and its image looks away from the bowl. This does not support the high tail as
a dense current bowl surface. Missing original SAM masks and selected clouds
prevent exact attribution to a mask, fusion association or sparse depth tail.
The old verdict stays false; the unsegmented cropped world map is not a new
segmented-object measurement.

For the four current-on cases, the measured robot orientation changes only
1.11–1.44 degrees between the pre-place and first endpoint capture. Three
t25 pre-place bowl midpoints are about 5.1cm to the right of the EEF, so the
split-place held-offset sends the EEF about 5.1cm left of the measured support
centre. Their endpoint bowl midpoints remain 4.0–6.1cm left and 3.3–4.6cm in
front of support centre. Orientation drift alone cannot explain this. Current
records cannot distinguish pre-place centre bias, carry slip, or segmentation
mixing; it would be incorrect to label any one of them proven.

The next original development capture needs selected-object SAM masks,
per-camera and fused segmented clouds, robot pose, target measurement and
held-offset at each carry segment, then both final frames. Drawer targets and
the placement segmentation ROI must use current geometry (`94b3a5b`,
`6b8de9b`). Query drawer independently in the t25/init2 saved public scene
before removing any cached cabinet fragment. Keep strict6 on>=0.90 and
in>=0.85 and the original support boundaries; no hidden support completion or
score change follows from this CPU analysis.
