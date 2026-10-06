# drawer4235 public endpoint-verifier diagnosis

The moving-face selector chooses a static cabinet interior plane after the
drawer opens. This is an entity-association error before the endpoint test,
not evidence for changing its 2.5 cm open threshold or disabling dual-view
fusion. The original verdicts remain unchanged: the five native-method cases
have four `false` and one `null` public results. The private endpoint labels
are true in all five, used only as diagnostic outcome booleans.

The CPU replay uses original LIBERO-90 task6, init10–14, from job4235 and
SOURCE556. It reads exactly 60 saved public RGB/world-map/calibration files,
listed with SHA256 in `public_inputs.json`, and starts neither a simulator nor
a GPU. Nineteen retained frame/moving fits reproduce the recorded point counts,
centres and normals exactly. The twentieth fit is init13's fused moving plane,
which runtime discarded because the two view-specific selections disagreed.
The positive-y front-axis hypothesis reproduces these existing measurements
exactly; no simulator axis or coordinate is used.

| Original init | Original public extension cm | Selected fused plane points | Selected points in current measured drawer bounds | Supported current-drawer plane points | Associated public extension cm |
| --- | ---: | ---: | ---: | ---: | ---: |
| 10 | 0.63 | 16325 | 0 | 12798 | 16.02 |
| 11 | 0.63 | 15574 | 0 | 14123 | 16.02 |
| 12 | 0.61 | 15628 | 0 | 12844 | 16.04 |
| 13 | null | 17506 | 17506 | 17506 | 16.01 |
| 14 | 0.73 | 16724 | 0 | 6645 | 15.93 |

The association diagnostic uses only the current drawer's measured AABB plus
5 mm. It does not alter runtime verdicts or claim an independent semantic
ground-truth mask. In all four false cases the selected plane has no points
inside that current AABB, whereas another already-valid plane has all its
points inside it. The candidate audit records both fits, their normal/residual
evidence and point support. The associated extensions use the same measured
frame and normal as the existing verifier.

`saved_public_replay/public_plane_binding_montage.png` shows init10 before and
after in both cameras. Red is the per-camera verifier's selected moving-plane
depth support; green is the current public drawer AABB's depth support; yellow
is their overlap. After opening, red marks the exposed static cabinet interior
while green follows the opened drawer. The overlay selects existing world-map
pixels; it does not generate new depth or simulator coordinates.

In init13, the primary view selects the static interior at y=-0.22375 m and the
wrist view selects the opened drawer at y=-0.05646 m. Runtime's 1.5 cm
view-disagreement check correctly rejects this approximately 16.7 cm identity
disagreement. In the other four cases both cameras choose the static interior,
so their agreement cannot detect that they agreed on the wrong surface.

## Exact source path

The execution snapshot is
`/public/home/sunyihan/rpent_libero_eval/source_v5_pan556_20261006`, commit
`d8b1d980603e6e0e8f7e14f9541c01f7686c7673`. The current local versions match
these three recorded snapshot hashes:

| Source file | SHA256 |
| --- | --- |
| robots/libero/v5_runtime.py | bc5001949752ba737e941d16f1244c153d61a6713879bf84d0dca4f969314dd5 |
| robots/libero/v5_fixture_parts.py | 3091478a6b6074d1dd1e588280f62c1ab89d5e07432b37f03395e42e54c3bdb6 |
| robots/libero/v5_verification.py | 753b8604c0955eeb1e5e4fa21e0c1747fdc390509a9bdac54f2dad5058e36e6f |

1. `Scene.measure_fixture_endpoint` in `v5_runtime.py:1096–1107` freezes the
   first parent/part measurement as `_drawer_endpoint_anchors` and passes those
   anchors, rather than the current drawer identity, to each later plane fit.
2. `measured_drawer_faces` in `v5_fixture_parts.py:303–365` restricts a full
   world map to the original side and drawer-height band, allows depth from
   3 cm behind the measured front to 35 cm in front, examines the five most
   populated 4 mm depth bins, and keeps the valid plane with most points.
   It does not require moving-plane support from the currently measured drawer
   or its handle. Opening exposes a denser cabinet-interior plane in that band.
3. `v5_runtime.py:1108–1141` fits both views and the joined cloud. It rejects
   conflicting selected planes, but cannot reject two matching static planes.
4. `measured_fixture_endpoint` in `v5_verification.py:199–231` correctly
   computes the selected face's distance to the measured fixed frame. It
   receives the wrong face, so it correctly returns a small extension for that
   face. The error is upstream of this endpoint threshold.

The smallest supported repair is to retain the independently anchored fixed
frame while binding each moving-plane candidate to the current measured
drawer/connected handle before comparing support. Absent or ambiguous current
identity should remain unknown. Selecting the most protruding plane alone
would not establish that it belongs to this drawer. No shared runtime has been
modified by this diagnosis agent.

## Reproduce the CPU analysis

```bash
cd /tmp
export PYTHONPATH=/public/home/sunyihan/rpent_libero_eval/source_v5_pan556_20261006
/public/home/sunyihan/rpent_libero_eval/.venv/bin/python \
  /public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer558_verifier_diagnosis_CPU_20261006/analyze_public_drawer_planes.py \
  /public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer558_verifier_diagnosis_CPU_20261006/public_inputs.json \
  /public/home/sunyihan/rpent_libero_eval/results/harness_v5/drawer558_verifier_diagnosis_CPU_20261006/independent_cpu_replay
```

The output directory must be new, preserving the existing saved-frame result.
`index_explicit_public_inputs.py` initially hashed the canonical artifacts from
the recorded attempt directory and endpoint source-step number. It performs no
directory scan. `public_inputs.json` is the self-contained immutable replay
input, SHA256 `bbe19b3087d0e1915a154042387f5eff9ef1965fdb8646de91a14d0f1a7e8640`.
The source audit was read at historical SHA
`61181758e0c598c9f1e224a0f7b503ac3b7ba85be292b91aa089916a5c69a1e2`;
its owner subsequently compacted the same-path summary. The original report
SHA remains `f3392d5a78e9dcf7623e8601c33ff4ce37908aa4a545a62afbbf29490a838fd0`,
and the original five ledgers are retained. Runtime replay uses the copied
public records in this package, not that later mutable summary.

These are five reused development states, not a confirmation cohort. No new
physical trials, training rows, qualification or COORDINATION entry are made.

## Independent current-part-window repair replay

`replay_current_part_bound_planes.py` tries the supported repair in an
independent CPU script. It leaves fixed-frame fitting on the original parent
anchor, uses the current public drawer's AABB plus 5 mm to select eligible
moving points, then applies the original height/side/depth gates, 4 mm depth
histogram, top-five-bin support rule and `vertical_face` tests. It retains
the original fusion disagreement tests and calls the unchanged endpoint
verifier. It neither picks the most protruding plane nor reads private outcomes
or coordinates for selection.

| Original init | Original public verdict | Repaired primary verdict / extension cm | Repaired wrist verdict | Repaired fused verdict / extension cm |
| --- | --- | --- | --- | --- |
| 10 | false / 0.63 | true / 15.95 | null | true / 16.02 |
| 11 | false / 0.63 | true / 15.96 | null | true / 16.02 |
| 12 | false / 0.61 | true / 15.95 | null | true / 16.04 |
| 13 | null | true / 15.94 | null | true / 16.01 |
| 14 | false / 0.73 | true / 15.94 | null | true / 15.93 |

The wrist-only endpoint remains unknown in every case because its before
capture has no independently measured fixed frame. The fused capture has that
frame from the primary view, and both moving-face measurements now agree.
The fused initial-frame distances remain approximately zero and the changed
after distances are 15.93–16.04 cm. Full per-view/fused fits for both phases,
all xyz window ranges and candidate support are in
`current_part_bound_public_replay/report.json`, SHA256
`dac256dabe5ab64876548aeedae49621275c19ca18d58b6f5de5550a020b0857`.

The immutable input SHA and source snapshot are the same as in the original
CPU replay. Run the independent repair script with those inputs and a fresh
output directory, as above. This saved-frame causal comparison supplies
evidence for root's runtime repair; it does not satisfy confirmation or
generalization requirements. Runtime remains unchanged by this agent.
