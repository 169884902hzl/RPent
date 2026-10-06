# Job 4150 precontact evidence and CPU repairs

Only the three explicitly registered `part0/attempt0` cases below were read.
Old physical outcomes, labels, clouds and receipts are unchanged. The geometry
audit used SOURCE547 (`1734afd085318efc2247c7be5b6405556313bb50`), not simulator
coordinates or BDDL. No SAM, planner or physical rollout was rerun in this audit.

| Original case | Public evidence | Supported development change |
| --- | --- | --- |
| drawer close, LIBERO-90 t0/init11 | Initial wrist face 15,413 points; after the old preapproach only 9.79% projects inside the wrist image. Current agentview still has a valid face/handle. | Keep normal standoff and orientation; raise the observation height, then recapture and remeasure. No plane threshold relaxation. |
| microwave open, LIBERO-90 t33/init2 | At frame0, two adjacent appliance parents share the same current door-cloud SHA. Proven aliases remained in public entities and blocked typed binding. At frame1 the door cloud is stale. | Retire proven aliases from public entities; retain immutable clouds and private alias mapping. Never reuse frame0 as a frame1 normal. |
| microwave close, LIBERO-90 t33/init3 | One current door, correct parent/frame, 36,589 points, plane residual P90 4.52mm. The original first handle query recorded zero accepted instances in both views. | Allow a current unique validated door cloud to orient a separately measured thin handle. This does not create handle recall or repair the recorded zero-instance query. |

## Observation pose projection

The CPU design experiment translates the actual frame1 camera only along world
z. Its rotation and xy location remain fixed. The smallest 5mm-grid lift with
at least 95% of both prior face and handle points in the central 80% of the image
is **10cm**. Face in-view coverage changes **9.79% -> 100%**; handle coverage
changes **95.66% -> 100%**; both central fractions change **0% -> 100%**.
The optical centre z changes 1.305441 -> 1.405441m. These are projections of
previously measured points, not proof of present visibility or physical success.

Runtime `stage_fixture_handle(..., observation_pose_v1=False)` enables this
development action only when requested. `MeasuredScene.drawer_observation_height`
fits this capture's drawer and handle RGB-D and predicts the fixed-orientation
camera transform from the measured EEF position. It changes only the safe
observation height; existing residual limits remain. The subsequent wrist
capture must pass the original current handle/plane measurement guards.

Repairs: `5b80c3b` alias retirement, `bd7b7f7` unique current door orientation,
`37aca79` optional observation height. Related focused tests: **188 passed**.
Physical validation remains the parent's SOURCE549 smoke. This audit admits no
skill recipe and submits no GPU job.

Exact projection command on gpu5880:

```bash
cd /public/home/sunyihan/rpent_libero_eval
PYTHONPATH=/public/home/sunyihan/rpent_libero_eval/source_v5_runtime547_20261006 \
  .venv/bin/python results/harness_v5/runtime542_readonly_audit_CPU_20261006/audit_job4150_drawer_observation_pose_CPU.py
```

| Artifact | SHA-256 |
| --- | --- |
| audit_job4150_precontact_CPU.py | 0e79e479e9c07f0a1152d85d3ccbb2290c487058a5244b822adebd99480fcecc |
| job4150_precontact_geometry_CPU.json | aae6eabba378c6f7af733d5dd4ffdfd9efc69ff06301d36661eea9bbd859ac09 |
| job4150_precontact_public_views.png | 521214e1a93f5c0b5e5ed17311e3faf15323210583fd362a4bd0d2ec1e5bc235 |
| audit_job4150_drawer_observation_pose_CPU.py | 414375f65d22a4e944a99677ccae780dfc44ab70c0712adcc7ae72a5d8520935 |
| job4150_drawer_observation_pose_CPU.json | 553fc836676a4b3cf7ff736d3a91d02c95730abc15eec054c9d4448386f420f9 |
