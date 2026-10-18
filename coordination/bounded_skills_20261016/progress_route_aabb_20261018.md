# Exact route AABB comparisons

Profile evidence before modification: `reports/visual_profile_startup_pair_20261018.json` records 153314 NumPy reductions /6.3267 seconds in the initial request (inclusive call tree). The implementation only replaces N-by-3 boolean reductions in two collision broad phases with the same six inclusive scalar-column comparisons. Mesh hull checks, clearance thresholds, IK order, candidate content and scores are unchanged.

CPU: 29 affected tests passed. Nine saved public screens from three states (can approach, bowl holding, cup approach), four routes each, all complete route-evidence dictionaries and collision-point outputs identical. Three jaw openings also matched at every screen. The isolated geometry comparison uses the same deterministic fake IK in both arms; it is not kinematic or physical validation. Sum of per-screen CPU medians: 2.474772 → 2.403564 seconds (2.88% lower), with small regressions in individual timings retained. Do not claim material episode acceleration.

Full real-startup request-byte and oracle-choice equality remains to be checked using this source snapshot. No training or confirmation admission. The raw CPU log is preserved; gzip is byte-exact. Existing unrelated Ruff findings in the two historical implementation files were left unchanged.
