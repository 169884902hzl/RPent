# Pre-lift contact identity

1. Bowl init17 fails before lift under source ff00387. Contact moves its surface while the stored precontact reference stays fixed; it is separate from the held-payload failures in init16/19.
2. Source c1bc859 registers the reference to current clean RGB-D, with the existing 0.1 rad / 15 mm bounds, and excludes additions matching the saved non-target scene within 4 mm. No hand-motion or private-pose correction is used.
3. Saved-state CPU comparison adds 30 current bowl pixels, removes none, and clears the lift route. Independent saved-pixel identities confirm all 30 are bowl. A rejected predecessor added 29 plate pixels; that result is retained and was never submitted to GPU.
4. CPU tests: 245 adapter/payload checks pass; the final 16 focused precontact checks also pass. One existing pytest timeout-configuration warning and seven existing Ruff findings remain. Physical success is not yet established for c1bc859.
5. The e5bbb18 init16/19 physical pair is closed: new2/2,legacy1/2. The same-launcher init17 startup9216_17 completed0:0 with203actual controls; formal9239_17 is pending Priority. The later68573bc geometry correction and startup9240_22 have separate identities; see progress_precontact_reciprocal_20261018.md. No training, confirmation or freeze admission.

## Cause and correction

The init17 saved capture has three current bowl edge points outside the original 1 mm precontact association. A bounded rigid fit estimates translation `[0.006049, -0.000177, -0.000054]` m and rotation 0.082817 rad; maximum original-point displacement is 7.814 mm. Current shared depth, not a jump in the partial-mask centre, establishes identity.

The first implementation af3953a recovered 59 current pixels but a CPU identity audit found 30 bowl and 29 plate pixels. It was committed for review but not physically admitted. The corrected implementation stores the precontact scene after exact target-pixel subtraction and 1 mm voxelization. Newly associated points within the existing 4 mm static-scene radius remain obstacles. The current raw target pixels are retained; registration without a saved stationary scene is disabled. The correction retains all 29 plate pixels while recovering the same 30 bowl pixels. Identity labels come from independent CPU simulator restoration only and are not used to select or reject runtime points.

Evidence: `reports/9026_17_precontact_membership_CPU_20261018.json`, `reports/9026_17_precontact_added_pixels_CPU_20261018.json`, `reports/9026_17_precontact_stationary_veto_CPU_20261018.json`, `reports/9026_17_precontact_stationary_identity_CPU_20261018.json`, `reports/precontact_stationary_validation_CPU_20261018.json`. Reproducer: `scripts/replay_precontact_surface_CPU_20261018.py`. Private identity audit: `scripts/9026_precontact_added_pixels_CPU_20261018.py`.

## Retained timing regression

The successful init10 pair from source87ef92e still costs1041simulation steps with the new rule versus434with the legacy rule. After the lower collision, new chunks execute release plus a23-tick wrist scan; the legacy rule stops after release. Current geometry after the scan selects a different approach orientation. Its lateral leg translates41.76mm and rotates1.44972rad, taking28.2836s. The legacy reapproach translates18.65mm and rotates0.09162rad on its lateral leg, taking1.28695s. The full new reapproach uses610ticks versus88. Its velocity-only lower bound is3.6243s; that lower bound omits acceleration/jerk and is not an achievable replacement duration.

The current trajectory code scales every leg's time by the largest derivative-limit ratio, so short lift/lower legs can slow an unrelated long turn. This source inspection identifies a possible extra cost, not a measured benefit from an unimplemented retimer. No speed, acceleration, jerk, force or budget limit is raised. Evidence: `reports/9211_10_reapproach_CPU_20261018.json`, script `scripts/diagnose_saved_reapproach_CPU_20261018.py`.

## Runtime and coordination

Source c1bc859 is pushed to harness-v5. Archive SHA `b9067c8fccf602dd8d9bbc4a30daeaba26013a19af4307e1a7a1816971533e22`. The snapshot is `/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_precontact_stationary_20261018_c1bc859`; entry `scripts.probe_bounded_feasibility:episode`, interpreter `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`. Public schema bounded-skills/3 and public-request-legal/2 bytes are unchanged. Candidate order is nonsemantic; detailed source history remains three receipts. The arbitrary-prefix CPU interface and its missing-historical-context limitation are unchanged.

The queue monitor also compared a startup element ID to array parent IDs, so its following array could repeatedly overtake the startup. It now recognizes both IDs. Startup9213_16 subsequently completed0:0 in3:17, with168actual control steps; its two-state physical array is9214. No running GPU task was cancelled. Node02/nice500 and Codex2's returning GPU share continue to govern admission.

The exact runtime replay with the same1mm stationary-scene voxelization independently reproduces30additions,0removals and all3recovered bowl blockers: `reports/9026_17_stationary_voxel_runtime_CPU_20261018.json`. Generic can init2/5 CPU checks under c1bc859 retain their failures. The later68573bc uses reciprocal pre-lift fitting and connected-depth completion to clear their saved-public routes; physical can success remains unverified and is not attributed to c1bc859.
