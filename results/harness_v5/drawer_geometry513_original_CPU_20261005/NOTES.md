# Original-task cabinet measurement diagnosis

Only the public measured entities and six explicitly selected RGB-D captures from job 3637 were used. No simulator object pose, BDDL goal or PRO task input was used. This is CPU geometry evidence, not an articulation success qualification.

The base configuration did not enable `fixture_handle_geometry_v3` or `fixture_drawer_clouds_v2`. In original Goal task 0/init 0 the main view contains three measured handle rows: 2,212/2,473/2,635 points, with widths 8.22/8.28/8.27 cm. The existing repeated-handle detector uniquely establishes front `(0, 1, 0)`. The closed cabinet alone has only 0.31 cm between its depth-band profiles and cannot establish the front using protrusion. The wrist view sees only one handle row; its absence of a full profile must not replace the main view's valid measurement.

Two defects in `fixture_parts` were reproduced on those public measurements. It redefined layer heights from the currently visible fragment, so the partial wrist capture advertised a cabinet top surface at z=1.035 m although the measured cabinet top is 1.127 m. The top drawer in the main capture had its centre at z=1.126 m because dense horizontal roof points dominated the band.

The correction anchors layer identities to the public measured cabinet bounds, excludes the top 1 cm from drawer faces, and rejects bands with less than 1.5 cm of current vertical support. Every returned coordinate remains a statistic of current measured points. After correction, the main top drawer centre is z=1.094 m and the independently measured top surface remains z=1.127 m; the incomplete wrist capture produces no invented top surface or front. Empty/currently occluded bands remain absent.

Original Long task 3/init 0 has a separate public drawer detection before setup. Selecting **current frame-0** pixels within its public bounds yields 52,514 points. Adding those to the cabinet establishes front `(0, -1, 0)` with 12.79 cm measured protrusion and a bottom drawer centre at y=0.117, z=0.942 m. This bounds-selection diagnostic is not a saved SAM mask and is not a runtime visibility claim. Enable current independently segmented drawer-cloud association to retain the initial front; after setup the main view is arm-occluded and the wrist contains zero cabinet points. Retreat and remeasure instead of reusing a moving drawer's old cloud.

`report/report.json` records the selected ledger lines, public entities, source/config hashes, all 18 RGB-D/metadata input hashes, camera-to-world origins, parameters, and exact before/after parts. The renderer's schema does not change, but measured entity selection/coordinates do; the runtime owner must register this development version before adopting it.

Reproduce with the repository interpreter:

```bash
PYTHONPATH=. .venv/bin/python results/harness_v5/drawer_geometry513_original_CPU_20261005/preparation/analyze_drawer_rgbd.py
.venv/bin/python -m pytest tests/unit_tests/robots/libero/test_v5_fixture_parts.py tests/unit_tests/robots/libero/test_v5_format_repair.py tests/unit_tests/robots/libero/test_v5_drawer_endpoint_geometry.py -q
```

Result: 41 focused CPU tests passed. The only warning is the existing unsupported pytest `timeout` configuration. Slurm submissions, runtime changes and physical articulation validation were not performed by this task.
