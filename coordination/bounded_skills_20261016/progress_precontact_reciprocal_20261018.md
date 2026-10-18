# Pre-lift occlusion diagnosis

Subsequent source/queue update: see `progress_precontact_support_20261018.md`. The queued 68573bc startup 9240_22 was superseded before execution by ec89f74 startup 9242_22; the historical measurements below retain their original sources.

1. One-sided registration rotates occluded reference surfaces toward the remaining visible silhouette. Two saved can states fit rotations of0.249/0.174rad despite actual diagnostic rotations of0.0040/0.0054rad.
2. Reciprocal correspondences restrict the correction to measured surface pairs. This is enabled only before lift; the held-payload estimator is preserved. Existing overlap, rotation, displacement and obstacle bounds remain unchanged.
3. The final source68573bc combines reciprocal fitting with existing connected-depth completion. Saved-public CPU replay clears all three lift routes: bowl init17 and can init2/5. These are zero-control geometry checks, not physical outcomes.
4. Final adapter/payload tests pass247/247;19focused checks also pass and overlap that suite. Independent CPU pixel identities confirm74/74new pixels belong to the target. Public schema/contract hashes are unchanged.
5. Source68573bc has no physical result yet; startup9240_22 is submitted after9239. The closed e5bbb18 pair is new2/2 versus legacy1/2. Sourcec1bc859 startup9216_17 completed with203actual controls; its pair9239_17 is pending. No training, confirmation admission or freeze claim.

## Cause and paired measurements

Only source-to-target nearest pairs were used in the fit. Once fingers hide part of a curved object, many hidden reference points converge on its visible silhouette. The apparent pose correction can exceed the existing0.1rad limit even though the object barely moved. Independent restoration of the unchanged simulator states is used only to diagnose this error, never to determine runtime ownership.

| Original state | One-sided fitted rotation | Reciprocal fitted rotation | Private diagnostic actual rotation | Private translation norm |
| --- | ---: | ---: | ---: | ---: |
| Can init2 /9026_22 |0.249290rad|0.008854rad|0.004017rad|0.190mm|
| Can init5 /9026_25 |0.174188rad|0.018717rad|0.005381rad|0.361mm|

The reciprocal fits' maximum corrections are0.709/1.334mm. The0.1rad/15mm final-transform limits,8mm support gate, minimum half-surface overlap and40correspondences are retained. No force, speed, budget or clearance changes are made. The original half-surface gate is evaluated before requiring reciprocal pairs.

Applying this estimator to held-payload motion failed an existing curved-surface regression (1failed/33passed). That implementation was rejected before any GPU admission. The correction is limited to pre-lift correspondence selection; the unchanged held-payload regression passes. The first failure remains part of the validation history.

| Saved public geometry | Baseline lift route | Candidate lift route | Membership additions/removals |
| --- | --- | --- | ---: |
| Bowl init17 |rejected|passed|31/0|
| Can init2 |rejected|passed|10/6372|
| Can init5 |rejected|passed|33/4612|

Removals are from the baseline's completed surface, rather than from raw current instance masks. Scene points formerly overcompleted as target remain obstacles. Reciprocal fitting alone left another can init5 finger blocker. The final correction reuses complete_spatial_payload_component on current raw dual-view depth:3mm connectivity, original measured spatial bounds, and the existing4mm stationary-scene veto. Independent CPU restoration gives zero state error and identifies all31/10/33added pixels as the target. No runtime private identity is used. A route pass is not a grasp-success measurement or full task result. The variant without voxelization did not resolve can init5 and was rejected.

Evidence: `reports/9026_22_precontact_reciprocal_fit_CPU_20261018.json`, `reports/9026_25_precontact_reciprocal_fit_CPU_20261018.json`, `reports/can_contact_motion_private_CPU_20261018.json`, the three `9026_{17,22,25}_reciprocal_membership_CPU_20261018.json` predecessor files, final `9026_{17,22,25}_precontact_component_CPU_20261018.json`, `reports/precontact_component_identity_CPU_20261018.json`, and `reports/reciprocal_precontact_validation_CPU_20261018.json`. Public-capture fixture: `tests/unit_tests/robots/libero/fixtures/public_precontact_occlusion_fit.npz` (every32rows, no private labels). Reproducers: `scripts/diagnose_precontact_fit_CPU_20261018.py`, `scripts/replay_precontact_surface_CPU_20261018.py`, `scripts/can_contact_motion_private_CPU_20261018.py`.

## Closed source-e5bbb18 pair

Bowl init16,9214_16: both arms succeed. New rule3decisions/244simulation steps/378.394s; legacy5/270/475.534s. Bowl init19,9214_19: new succeeds with5decisions/432simulation steps/647.212s; legacy fails with12/414/862.661s. Legacy carry_to candidates are all collision-rejected; wrist scan is rejected at0controls, refresh reports no scene change, then the oracle has no acceptable option. These are two targeted development pairs, not category success rates. Source remains e5bbb18 and is not relabeled as the reciprocal candidate. Evidence: `reports/chunk_v3_final_fit_20261018_paired_latest.json`. Original ff00387 cohort likewise keeps its source and denominator.

## Source and queued physical checks

Commit68573bc5fe3a752ce8bfb6034a89ea2eb5606fab is pushed to user-fork/harness-v5. Snapshot `/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_precontact_component_20261018_68573bc`; archive SHA`a18a58c10f614242927cbdb198d1c617acd61f5d5c32df39311971808b69867a`. Entry `scripts.probe_bounded_feasibility:episode`; interpreter `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`. All220registered original states pass CPU preflight. Startup9240_22 waits for9239; only after a successful actual physical request may the same launcher admit formal22/25new/legacy pairs. It has no physical outcome at this update.

The prior c1bc859 startup9216_17 is COMPLETED0:0,203actual controls; formal9239_17 is pending Priority. The one active controller continues that pair. The new controller is not started concurrently. On the refreshed old-sourceff00387 cohort,50/68completed original-state oracle episodes succeed: bowl15/20, alphabet-soup can14/20, container18/20, cup2/6, drawer-close1/1, stove-off0/1. Remaining episodes are incomplete and unscored. Labels box_transfer refer to the alphabet-soup can, not the cream-cheese box. This cohort is not physical evidence for68573bc.

Schema bounded-skills/3 SHA`df17c6c49e4992247ab8ff37ebf528f893ac6887ea8cf946e25668aca110b4aa`; public-request-legal/2 contract SHA`7e898e3bd4e8f4c7a4e9951d897cc1fe682037ee35ee4d6d5cc1f52606e2f49c`. Candidate order is nonsemantic; detailed source history is three receipts. The arbitrary-prefix CPU interface still requires its matching saved measured context. Missing historical contexts remain unsupported.
