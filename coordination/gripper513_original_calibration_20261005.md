# gripper513: original-task robot sensor calibration

Accepted parent ownership: CPU-only robot calibration and public gripper geometry. Parent owns runtime integration, Slurm submission and shared COORDINATION/push. No task-score run, new training rows, PRO configuration, hidden text or object-truth runtime input.

Completed opening calibration on six representative original-task resets (bowl, mug, bottle, box, moka pot, frypan), 30 open + 30 close + 30 reopen control steps each. All 540 samples retained, all policy proprio dimensions 39, and zero finger-to-scene contacts. Last 10 samples per phase provide 120 empty-open and 60 empty-closed observations.

| Quantity | Measured metres |
| --- | ---: |
| closed_empty_max_m | 0.0018488315399736166 |
| open_empty_min_m | 0.07815118134021759 |
| max_sensor_opening_m | 0.07900479435920715 |
| tolerance_m (maximum observed tail range) | 0.000853613018989563 |

`minimum_points_per_finger=null`: point-count evidence at both fingers has not been calibrated on original perception data. The public verifier now returns unknown for this case; it does not silently convert null to a numeric threshold. Opening and static-geometry calibration is not the ≥95% independent grasp-verifier confirmation.

The installed public Panda gripper MJCF gives `rotation_body_to_site=Rz(-90°)`, `offset_body_to_site_m=[0,0,0.097]`. `robot0_eef_pos` already measures the grip-site position, so this offset must not be added to that position. Pad-centre offset from site is `[0,0,-0.0036]` metres, closing axis 0, pad depth/height half sizes 0.008 m, joint-opening to inner-pad-gap offset -0.001 m. The pad model does not cover the entire finger mesh.

For parent integration, `R_world_site=R(robot0_eef_quat) @ rotation_body_to_site`, and `finger_origin_world=robot0_eef_pos + R_world_site @ finger_centre_offset_from_site_m`. Only existing robot proprioception and public rigid geometry are required. The disabled site-quaternion sensor was read directly for a CPU diagnostic; it was never enabled or added to π0.5 observations.

Robot-only synchronous sensor validation passes: rotation residual 3.122481458263474e-7 rad, position residual 3.469446951953614e-18 m, proprio 39. Initial diagnostic geometry3/4 mixed the cached step observation with an immediate sensor, causing 0.000669 rad and 0.000194 m residuals during settling; logs retained. Geometry5 reads all robot-only sensors at one instant. cpu_run1's missing disabled site-observation failure is also retained. Opening cpu_run2 is unchanged.

Artifacts on gpu5880-ts, beneath `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/gripper513_original_opening_calibration_20261005/`:

| File | SHA-256 |
| --- | --- |
| cpu_run2/report.json | c581fe89f61da1113839a64b35f095b8d73b856f870d78997a5efdae4ee31787 |
| cpu_geometry5/report.json | 0efd6b556b37beaedb3d6ade9ec2a56f79dfc845196afe0b6043becbc4f21b4b |
| runtime_calibration.json (compact, identical calibration/geometry) | d4d977a5e5c23a23d80983ab34a4958373c6103035c2156ced24038204e4ca1c |
| installed public panda_gripper.xml | 066fd7ae45afb11e1844869360e587646e9768210ba5389aa3cd35292cde29c1 |
| smoke.json manifest | 99d06df0d8c187db4d4f75df632d495cfd3bd80f282a58cd8c0e264de03ad1e3 |

Source SHA-256:

- scripts/probe_v5_gripper513_calibration_cpu.py: fd52c995a597673e74b68edfb44f13e41500149dac6671b72933fb29a9ebb64a
- robots/libero/v5_grasp_measurement.py: 700e2f5984c1fb911e639aa38e5915cdbd76965384ec8fce8be60fc94a38f37f
- tests/unit_tests/robots/libero/test_v5_grasp_measurement.py: f5906718ee2c9e5ef4f6ff621b4bca274c0e2fbcd4861b6907f16921aa2a34c7

Actual successful CPU command (gpu5880-ts; no Slurm/GPU):

```bash
cd /public/home/sunyihan/rpent_libero_eval/source_v5_grasp512_mug_unvisited_resume_20261005
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=/public/home/sunyihan/rpent_libero_eval/source_v5_grasp512_mug_unvisited_resume_20261005
export MUJOCO_GL=osmesa PYOPENGL_PLATFORM=osmesa LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH=/public/home/sunyihan/rpent_libero_eval/runtime_config
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
/public/home/sunyihan/rpent_libero_eval/.venv/bin/python -u \
  /public/home/sunyihan/rpent_libero_eval/scripts/probe_v5_gripper513_calibration_cpu.py \
  --manifest /public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp451_sustained_truth_20261005/preparation/smoke.json \
  --enrich-existing /public/home/sunyihan/rpent_libero_eval/results/harness_v5/gripper513_original_opening_calibration_20261005/cpu_run2/report.json \
  --output /public/home/sunyihan/rpent_libero_eval/results/harness_v5/gripper513_original_opening_calibration_20261005/cpu_geometry5 \
  > /public/home/sunyihan/rpent_libero_eval/results/harness_v5/gripper513_original_opening_calibration_20261005/cpu_geometry5.log 2>&1
```

The original opening command uses the same environment and manifest, omits `--enrich-existing`, and targets `cpu_run2`. The compact JSON is a deterministic extraction of the enriched report's source identity, opening calibration, geometry and robot-only validation; original full reports are preserved.

Verification: `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/unit_tests/robots/libero/test_v5_grasp_measurement.py`: 14 passed. A local pytest configuration warning about missing timeout plugin does not affect these unit results. No new physics qualification or performance claim.
