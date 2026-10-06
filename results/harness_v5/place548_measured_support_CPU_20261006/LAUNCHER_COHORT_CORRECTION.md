# Launcher cohort correction

The initial `place_smoke40.json` (SHA
`f23ceede646ad3742481221532705aa859cb353f3f8910e6b7868f5bfac47b1e`)
passed only the explicit-file and registered-state helper preflight. It did
not pass the actual skill535 launcher, which accepts `cohort=selection` for
these reused development states. The original producer incorrectly emitted
`development_smoke`; the launcher rejected it before submission and physical
execution. The original manifest, producer and helper output are preserved.

`prepare_smoke40_selection_v2.py` emits the compatible `selection` cohort,
retaining the original deterministic 40 requests, reused-state warning and
`qualification_authorized=false`. Its output is the independent
`place_smoke40_selection_v2.json` (SHA
`60b904989c1f81bccf6ebbd744c180bd3cd494a7f7b4938b969fbb6ecc8599c2`).
It is a corrected preparation example, not a new submission.

Root owns the actual SOURCE548 run and its source-provenance manifest
`place_smoke40_selection_source548.json`. Root runs all eight shards through
the real launcher with `SKILL535_PREFLIGHT_ONLY=1` before submission:
`/public/home/sunyihan/rpent_libero_eval/source_v5_runtime548_20261006/scripts/run_v5_skill535_place_confirmation.sbatch`.
The helper-only preflight does not establish launcher readiness.
