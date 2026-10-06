# stove560: fixed control-centred SAM smoke preparation

This is a public-measurement development smoke, not an endpoint qualification.
It retains all twelve saved original Goal7 init0/5 views used by job4240. No
simulator, GPU service, private labels or PRO inputs were opened during CPU
preparation. Shared runtime and the stove555 source snapshot remain unchanged.

The crop proposal comes from stove559's full-frame RGBmax64 components,
constrained by the measured stove shell and original RGB-D. Ten views have one
component. Their entire observed component rectangle (raised bar and base rim)
is padded by 25% per axis and at least 20 pixels, then clamped to the saved image.
The crops are fixed in the manifest before any new SAM result is observed.
The two views without a component remain `missing_control_bbox`; they receive
neither invented geometry nor substitute views. The montage shows all twelve.

Only the twenty new control-crop queries will run: ten crops times the original
`stove knob` / `stove switch handle` queries, minimum score 0.2. Job4240's forty
eight full/body-context50 query records are read explicitly and SHA checked,
not recomputed. The original stove555 `measured_stove_control_pose` implementation
and thresholds are reused. Query hits and candidate angles are not on/off truth;
every endpoint stays `unmeasured`. The saved init0 on/post and off/before views
are identical and do not count as independent trials.

RGB may be resized to longest edge 1024. Depth/world samples are never
interpolated. SAM masks return by nearest-neighbour to the original ROI and
index the original world map. The mapper records high-resolution calibration,
pixel-centre transforms and the unchanged camera extrinsic.

## Registered identity and actual CPU check

- Source snapshot: `/public/home/sunyihan/rpent_libero_eval/source_v5_stove555_20261006`.
- Geometry evidence commit: `fad9337ddb6d70ff25e0aa91495df7bd349db11f`.
- Manifest: `control_crop_sam_manifest.json`, SHA256
  `bdbfc3d9eab3b8240a6514013832b06b6231a1d88957c5d9cd04dd45308b3dbb`.
- Launcher: `run_offline_control_crop_sam.sbatch`; 1 GPU, no node binding.
- Entrypoint: `offline_control_crop_sam.py` with remote `.venv/bin/python`.
- CPU check output: `launcher_cpu_precheck/preflight_jobcpu_precheck.json`.

The actual remote launcher ran with `STOVE_CONTROL_PREFLIGHT_ONLY=1` and
`SLURM_JOB_ID=cpu_precheck`. It changed cwd to `/tmp`, checked producer/source/
baseline/input hashes, retained twelve views, and passed all ten all-foreground
pixel-to-original-XYZ equality checks. No GPU service or simulator was started.
The same preflight runs before the GPU entrypoint. A query error is recorded in
the flushed ledger and causes a nonzero exit.

Actual CPU command:

```bash
env STOVE_CONTROL_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove560_control_crop_CPU_20261006/control_crop_sam_manifest.json \
  STOVE_CONTROL_MANIFEST_SHA=bdbfc3d9eab3b8240a6514013832b06b6231a1d88957c5d9cd04dd45308b3dbb \
  STOVE_CONTROL_OUTPUT_ROOT=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove560_control_crop_CPU_20261006/launcher_cpu_precheck \
  STOVE_CONTROL_PREFLIGHT_ONLY=1 SLURM_JOB_ID=cpu_precheck \
  bash /public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove560_control_crop_CPU_20261006/run_offline_control_crop_sam.sbatch
```

Prepared GPU command for the owning root agent to register and submit:

```bash
sbatch --export=ALL,STOVE_CONTROL_MANIFEST=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove560_control_crop_CPU_20261006/control_crop_sam_manifest.json,STOVE_CONTROL_MANIFEST_SHA=bdbfc3d9eab3b8240a6514013832b06b6231a1d88957c5d9cd04dd45308b3dbb,STOVE_CONTROL_OUTPUT_ROOT=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove560_control_crop_SAM_original_20261006 \
  /public/home/sunyihan/rpent_libero_eval/results/harness_v5/stove560_control_crop_CPU_20261006/run_offline_control_crop_sam.sbatch
```

Outputs are `preflight_jobJOBID.json` and `control_crop_jobJOBID/` in that output
root. Each query preserves scores, full-frame masks, original world points,
unchanged-geometry rejection evidence, wall time and explicit source hashes.
The ledger has twenty RPC rows plus four missing-view/query rows. Missing views
also receive per-view summaries. This CPU package does not submit a job or write
COORDINATION; the root agent owns both.

`prepare_control_crops.py` reproduces the fixed manifest and montage on the
local workstation using only explicit saved public RGB paths. It intentionally
does not scan artifacts. The remote GPU producer uses the manifest's direct
absolute input paths, not the workstation cache.
