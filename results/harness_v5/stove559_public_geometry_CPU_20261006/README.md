# Original public stove geometry CPU diagnosis

The existing saved RGB-D contains a separable black circular control base, a
raised narrow handle and an independent fixed stove-body edge. Pure CPU
geometry yields seven candidate directed angles in twelve fixed views. One
same-capture main/wrist pair agrees within 0.54 degrees. This supports another
bounded public-measurement smoke, not an on/off endpoint or skill qualification.
Every endpoint in this package remains `unmeasured`.

The inputs are the explicit original Goal7/init0 and init5 captures already
listed in SOURCE555's `offline_crop_sam_manifest.json`, SHA256
`122de1d0048033c2334044f849e61738384f0c98970e801cfd80be74aa226069`.
There are six protocol captures and twelve views; on/post-recovery and
off/before-contact have identical saved images. These are repeated development
observations, not independent trials. No PRO files, private labels, simulator
geometry or coordinates, sealed inputs or manual instructions are opened.

Job4240 completed all 48 SAM calls without an execution error. The copied
`summary.json` and `queries.jsonl` remain unchanged. Both full and 50% body-crop
profiles accept one query in the same init5/off/post-recovery wrist frame.
The crop raises its score from 0.359375 to 0.7734375 and its mask pixels from
19656 to 19702, but adds no measured control view. The handle query returns
no instances. Crop confidence alone does not repair coverage or direction.

## Public geometry path

1. `inspect_full_frame_dark_components.py` uses the full saved image, three
   fixed RGB-max thresholds (40/64/80), measured proximity to the existing
   stove AABB, a measured height range and pixel connectivity. It retains
   components outside the measured stove's xy extent with visible size at
   most 13 cm and component-AABB gap at most 7 cm. The per-pixel search is
   wider (15 cm), preserving the far half of an attached control. The first
   7 cm per-pixel exploration clipped that half and is retained on disk.
   These constraints locate candidates; they do not establish semantic truth.
2. `fit_full_frame_public_control_parts.py` fits a circle to actual measured
   xy-boundary samples, then selects the observed raised patch using the
   existing 4 mm upper-patch depth idea. The circle requires at least 180
   degrees of observed boundary support. The upper patch must be planar,
   near-horizontal and elongated. Its direction remains ambiguous unless
   centroid offset and unequal endpoint support agree and exceed conditional
   circle-fit noise. The script never reads procedural on/off names to choose
   polarity, nor a private outcome.
3. `measure_public_shell_reference.py` uses the existing same-capture
   **main-view stove SAM mask and its original world points**. It finds a
   supported long convex-hull edge, chooses the unique nearest edge to the
   measured control base and orients its normal toward the measured body.
   This is independent of the black control segmentation. It replaces the
   earlier exploratory reference to the measured body AABB centre.

At RGB-max64, ten views contain a dark control candidate and seven supply all
three candidate geometric parts. The other views have absent/occluded controls
or insufficient base/handle support. Raising the colour threshold to 80 also
admits spurious dark regions; the circle/handle checks retain their ambiguity.

| Original capture | Main candidate angle to measured body edge | Wrist candidate angle |
| --- | ---: | ---: |
| init0 on/before-contact | 178.37 degrees | unknown |
| init0 on/post-recovery | -72.97 degrees | unknown |
| init0 off/before-contact | -72.97 degrees | unknown |
| init0 off/post-recovery | -96.33 degrees | -96.86 degrees |
| init5 on/post-recovery | -64.10 degrees | unknown |
| init5 off/post-recovery | unknown | -68.50 degrees |

`public_geometry_montage.png` marks actual observed base-rim points in cyan,
the observed upper-patch axis in orange and the measured body edge in yellow.
The model arrow is shown only when the conditional polarity checks pass.
Green boxes locate the measured dark component. All projections use the
recorded camera calibration and actual high-resolution image dimensions.

## Limits and next supported experiment

Colour thresholds 40/64/80 yield 8/7/7 candidate directed views. The largest
supported circle-centre spread across those thresholds is **1.24 cm**. Circle
bootstrap values quantify noise conditional on a selected model and do not
capture this model-selection bias. Seven candidate angles therefore must not
be promoted directly to a qualified runtime endpoint. The one dual-view
comparison is useful geometric evidence and supplies no overall accuracy claim.

The body-centred 50% crop clips init0's initial handle tip. Full saved-frame
geometry restores its visible direction. A supported next SAM experiment is a
control-centred crop derived from the public component bbox plus fixed context,
preserving the complete base and handle. Keep the original knob/handle queries
and score threshold 0.2 first, so that the change tests localization. Return
crop masks to original pixels and index unchanged world points using the
existing crop helper. Retain FOV failures and ambiguous geometry. Do not launch
the 100-cell qualification driver from this small analysis.

`public_indicator_pixels.json` additionally records a visible appearance cue:
red pixels within the existing stove mask are zero initially and about 8%
after both the on and subsequent off attempts. That observation is not
silently converted into an on/off label; requested endpoints remain uncalibrated.

## Reproduce locally

The original referenced RGB/world/calibration/mask files were retrieved
explicitly into `stove555_live_CPU_20261006/remote_public_inputs/`; each read
checks its recorded SHA. From `/home/agilex/cobot_magic/rpent_libero_eval`:

```bash
.venv/bin/python results/harness_v5/stove559_public_geometry_CPU_20261006/inspect_full_frame_dark_components.py
.venv/bin/python results/harness_v5/stove559_public_geometry_CPU_20261006/fit_full_frame_public_control_parts.py
.venv/bin/python results/harness_v5/stove559_public_geometry_CPU_20261006/measure_public_shell_reference.py
.venv/bin/python results/harness_v5/stove559_public_geometry_CPU_20261006/render_geometry_evidence.py
```

`geometry_evidence.json` contains per-view inputs, circle/handle evidence,
three-threshold checks, same-capture reference edges and paired-angle results.
`geometry_summary.json` records counts and limitations. The manifest pins only
the explicit small CPU evidence/producers; original world maps are referenced
with hashes and are not committed. Shared runtime and SOURCE555 remain unchanged.
