# Fresh RGB-D contact verification development

The adapter now verifies an anchored nudge from a fresh pair of public depth captures even when SAM loses or caches the contacted entity. Entity-centre displacement remains a separate diagnostic. A stale depth capture remains unmeasured. The existing receipt evidence list records the paired capture IDs and compatible axis-displacement interval; schema stays `bounded-skills/1`. The 4 mm collision clearance, 5 mm progress threshold, force, speed and control budgets are unchanged.

## Exact saved-public drawer comparison

The old `9368299` drawer-open run `8145_100` has four misclassified contact motions. Recomputing its exact saved public RGB-D under `bc160ff` uses the already committed handle-extent repair. No new simulator controls or private labels enter this recomputation.

|Decision|Old handle-reference points|New handle-reference points|Old receipt evidence|New compatible axis interval|
|---|---:|---:|---|---|
|2|1,195,059|90,468|No effect, -1 to +1 mm|18 to 20 mm|
|3|535,873|60,134|Skipped because entity identity was stale|18 to 20 mm|
|4|536,368|59,960|Skipped because entity identity was stale|8 to 10 mm|
|5|536,234|75,905|Skipped because entity identity was stale|8 to 10 mm|

The private, zero-control prefix diagnosis separately measures joint displacements of approximately 19, 19 and 9 mm for the first three moves. Those labels are diagnostic only. The fourth post-state was not in that captured private prefix. Public intervals are geometric ambiguity ranges, not confidence intervals.

The original complete drawer-open episode is natively successful: 11 decisions, 597 control steps, 1174.32 seconds. Its full result is retained under its original source; correcting receipts does not create a second independent task success.

Reports: `reports/handle_reference_pair_CPU_20261018_drawer8145.json` and `reports/drawer8145_private_prefix_CPU_20261018.json`. Source entry is `MeasuredSkillAdapter._execute_one`; reproducible measurement entry is `scripts/drawer8145_handle_reference_pair_CPU_20261018.py`.

## Plate diagnosis, no deployed repair

The original upper-rim contact produces only 0.357 mm planar displacement at the saved contact state; a measured lower rim produces 15.421 mm, including only 9.451 mm along the attempted y direction. Four-axis low-rim tests initially reused stale IK and finger positions. The corrected diagnostic rebuilds both from current public proprioception for every nudge: two closure sweeps are collision-rejected; the other two complete four nudges but advance the plate only 11.345 mm and 0.639 mm along their respective inward axes. This is insufficient sustained contact and is not deployed. A separate 30/45-degree oblique-rim pilot retains the same screening and control limits: two x-side approaches are IK-rejected and two y-side closure sweeps are collision-rejected before control. All four execute zero controls. No contact-planner change is deployed.

Reports and scripts preserve each diagnostic revision. CPU physics restoration residual is zero. These frozen-sensor physics pilots do not perform online post-action RGB-D sensing and are not complete-task scores or confirmation evidence.

## Validation and resource contract

Pushed runtime: `cbffa78f6fc06b0275e61899b30a64656dc1e635`. Full adapter regression: 162 passed in 81.21 seconds (`/tmp/bounded_fresh_contact_tests_20261018_r5.log`); focused nudge checks: 19 passed, included in that total. Focused Ruff excluding pre-existing CPY001 and diff checks pass.

New regression cases cover missing/cached SAM identities, fresh-depth motion, stale raw captures, true raw occlusion, stationary contact, opposite motion and ambiguous geometry. Test fixture sensor captures use a distinct capture index and preserve explicitly supplied collision clouds. All raw failed test logs are retained under `/tmp/bounded_fresh_contact_*20261018*`.

All GPU work uses node02 with `Nice=500`. Three serial dependency lanes keep aggregate Codex3 concurrency at three; node01, protected c5/c6/rf jobs and historical held jobs remain untouched. No training, PRO inputs, confirmation rerun or change to permanent training exclusions is involved.

## Immutable deployment

Runtime snapshot: `/public/home/sunyihan/rpent_libero_eval/source_bounded_cbffa78_20261018`.
Code archive SHA256: `5cf7e48709e96362275e6ee13d6ee419737e5f7a07e880c70aeda0ab9d1d73a6`.
Manifest: `/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/feasibility_20261017/preparation/original20_manifest_fresh_contact_20261018.json`, SHA256 `faf0c7fd0125333a0506021e66bcd86c5f7a2839cdd96a7547e65915c6f0912b`.
CPU preflight verifies all 220 registered original states. Entry: `scripts.probe_bounded_feasibility:episode`; interpreter: `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`.
Same-source/same-launcher drawer startup: `8160_100`, running on node02 after the prior stove episode finished. Full drawer is not submitted until this produces a physical request and exits cleanly. Submission: `reports/fresh_contact_submission_20261018.json`.

Codex1/Codex2 notice appended to shared COORDINATION at bytes 6901205720–6901208549; append SHA256 `341dc44187a31ea979e57c657116157e458d3b0a3a9e33669138a29c3585c794`. This explicitly records the receipt semantics update. Raw log is not read or rewritten.
