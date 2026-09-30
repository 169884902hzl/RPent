# Public binding repair — development evidence

The explicit 20 first-choice records come from original-task expert shard2709,
source18e2fac. They preserve the actual public requests, measured geometry,
choices, receipts and old results. The two replay outputs are binding diagnosis,
not physical task scores. Five Spatial references newly resolve: task1/6/7/8/9.
The old expert200 gate and original A1-N records are retained without edits.

The expert now resolves a unique nearest instance for `next to`, and unique
measured `on`/`in` relations using the same 2cm public relation rule. It handles
public drawer ordinals and a measured table centre, but does not invent a table
anchor when segmentation has not provided one. Small visible-surface extents
alone no longer exclude an arbitrary black bowl when the instruction does not
refer to a ramekin. `reperceive` retains the initial scene vocabulary and can
retry categories with no initial detection.

Still unresolved in these records: missing cookie-box/cabinet/ramekin reference
measurements, no measured table anchor, absent cream-cheese/butter/pudding/milk
categories, and multiple bottle detections for the same queried category.
No private object instance, true object coordinate, or private predicate is
used as a substitute for a missing public binding.

CPU validation:22 focused tests and Ruff pass. Existing `timeout` pytest option
is unavailable in the local test environment; this is not an integration test.
The independent six-episode Slurm reproduction uses the same episode identities
as the retained failures/control and unchanged100decisions/40chunks/10000steps.
Its physical result is pending until the new source runs. Formal data remains0.

CPU commands:

```bash
.venv/bin/python -m pytest tests/unit_tests/robots/libero/test_v5_oracle_policy.py tests/unit_tests/robots/libero/test_v5_runtime.py tests/unit_tests/robots/libero/test_v5_state.py -q
git show 18e2fac:robots/libero/v5_oracle_policy.py > /tmp/rpent_v5_oracle_18e2fac.py
PYTHONPATH=. .venv/bin/python results/harness_v5/binding_repair_20260930/replay_bindings.py --policy /tmp/rpent_v5_oracle_18e2fac.py --records results/harness_v5/binding_repair_20260930/recorded_first_choices.json --output results/harness_v5/binding_repair_20260930/replay_before.json
PYTHONPATH=. .venv/bin/python results/harness_v5/binding_repair_20260930/replay_bindings.py --policy robots/libero/v5_oracle_policy.py --records results/harness_v5/binding_repair_20260930/recorded_first_choices.json --output results/harness_v5/binding_repair_20260930/replay_after.json
```

Hashes of repaired source, launcher, explicit manifest and input records are
in `hashes.json`. Future serializer316753ea alignment is still required before
harness freeze or formal LIBERO data delivery; it is not claimed by this repair.
