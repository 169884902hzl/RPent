# Public visual-self-filter optimization

The conservative base-frame broad phase leaves the original expanded local box and convex-hull predicates unchanged. No candidate pruning, collision threshold, robot limit or task selection changed.

Saved public RGB-D checks: 4 states × 2 views; every output array and evidence dictionary was exactly equal in 4 alternating runs. Sum of 8 median kernel times: 20.236033 → 13.480120 s (33.39% reduction). This is a kernel result, not an episode throughput claim.

CPU regression: 20 passed, one existing pytest unknown-timeout configuration warning. Commands: `.venv/bin/python -m pytest -q tests/unit_tests/robots/libero/test_bounded_self_filter_equivalence.py tests/unit_tests/robots/libero/test_bounded_motion.py tests/unit_tests/robots/libero/test_bounded_perception_profile.py`; `git diff --check`.

Next: same-source same-launcher physical startup with perception profiles; compare its complete public request bytes and oracle selection to the unchanged initial state. Training and confirmation are disabled.
