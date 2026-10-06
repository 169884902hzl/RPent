# Place548 development preparation

The strict-v6 placement path resolves `on(cabinet)` to a unique public
`measured_top_surface` child associated by `part_of`. Both geometric place and
full contact-subtask verification use this support. The contact prompt keeps
the originally selected cabinet. Existing pre-occlusion target-cache entries
take precedence for the same support ID. Missing or ambiguous support remains
unmeasured; no simulator region is used and verifier thresholds are unchanged.
Legacy strict-v5 behavior is unchanged.

Frozen SOURCE544 coverage (306 complete records): current-arm cabinet selectors
59/59 and full-subtask selectors 29/29 have exactly one current visible top
surface; all 88 also have that associated surface in the pre-grasp public
snapshot. Actual internal cache contents were not serialized, so availability
before grasp is not presented as proof of a specific internal cache entry.
The old current arm used strict-v5; full subtasks used strict-v6.

CPU public-prefix routing: 88/88 resolve the expected support, 59 route to
geometric placement and 29 to the unchanged original-selector subtask prompt;
zero exceptions. Movement and contact functions stop before execution. This is
a routing check, not a physical-success result. 18 new focused tests passed;
combined selected placement regression tests passed 38/38.

The 40-request smoke selects the first five preregistered states for each of
LIBERO-90 tasks 2, 24, 10 and 25, for each arm (20 unique states). Selection
does not inspect outcomes. Both arms use strict-v6, fixture-in contact, the
same pinned perception/fusion settings and 160 action chunks. It reuses
selection states for development and cannot grant qualification.

CPU preflight checked 107 explicit files and all 40 registered state hashes.
No new Slurm job is submitted by this preparation.

| Artifact | SHA-256 |
|---|---|
| place_smoke40.json | f23ceede646ad3742481221532705aa859cb353f3f8910e6b7868f5bfac47b1e |
| cpu_preflight_state.json | e176a29681ff4598f5bcd5cd81272e38bad7e45b41c7a8740d1175e18336c099 |
| support_coverage_source544_306.json | 589e7ae93e1678562b7fba37de490c37c29424886edc7cebfc5601214a44bc44 |
| public_support_routes_CPU.json | 89bea7d941c494ca1740570246bac06b618b11feb69b1853fc58b7f39879bdcd |
| prepare_smoke40.py | 00e5936eeb41928d14123b3afc56b8123458e5c8eb1b6302d39538a41532c0b9 |
| inspect_public_support_coverage.py | 2675416c8d11e5fe050dfb09a1319d59fb552eb1f7a9edb2e3b661e10643f96f |
| replay_public_support_routes.py | e8b905d3fdab986a1a8a5ed34d3c4a9b9054802d707b3aeaae640ce5d297b551 |

Remote directory:
`/public/home/sunyihan/rpent_libero_eval/results/harness_v5/place548_measured_support_CPU_20261006/`

CPU preflight command (SOURCE547 contains the same preflight loader):

```bash
cd /public/home/sunyihan/rpent_libero_eval/source_v5_runtime547_20261006
PYTHONPATH=. /public/home/sunyihan/rpent_libero_eval/.venv/bin/python -m scripts.v5_probe_preflight --manifest /public/home/sunyihan/rpent_libero_eval/results/harness_v5/place548_measured_support_CPU_20261006/place_smoke40.json --states
```
