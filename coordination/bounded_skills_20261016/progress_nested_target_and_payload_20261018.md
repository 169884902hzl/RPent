# Original-scene target binding and held-boundary development

Simulation development only. The private oracle chooses existing public candidate IDs, with pi0.5 disabled. CPU perception/planning replays and startup checks do not enter full-task denominators. All old failures and permanent confirmation exclusions remain unchanged.

## Nested target identity

Source d6c768c fixes a duplicated basket in the first request of job8061_20. Two same-category masks have IoU 0.563972, but cover 99.8548% of the smaller mask; 99.9221% of the larger mask belongs to depth components supported by their intersection. The existing IoU-only check retained both and the private selector could not bind the destination. The new check requires high containment plus shared current depth connectivity. Disconnected neighbouring objects remain separate. A duplicate keeps the highest-confidence complete measurement and its matching per-view evidence.

Exact saved-mask CPU replay changes two basket entities / no unique binding into one basket entity / unique binding e99, retaining confidence 0.828125. This is not a physical task score. Reports: `reports/box8061_nested_before_CPU_20261018.json` and `reports/box8061_nested_after_CPU_20261018.json`.

Runtime/work-surface/bounded-skills/payload CPU validation for d6c768c: 321 passed in 58.27s. After a test-style-only edit, the seven affected cases passed again. The broader count and subset overlap. Ruff comparison found zero new findings; existing runtime findings were preserved.

Snapshot: `/public/home/sunyihan/rpent_libero_eval/source_bounded_d6c768c_20261017`. Archive SHA256: `122fa213fc5c18b9c40f46475f3fbfb54103c5025f973bde9f089340b3a466c9`. Entrypoint: `scripts.probe_bounded_feasibility:episode`. Interpreter: `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`.

The identical-snapshot/launcher startup8064_20 executed 280 controls: move_to226, align7, descend47, all with successful receipts. Full job8065_20 then started. A successful startup is excluded from the task denominator.

## Closed representative failures

|Source/job|Category/state|Native success|Decisions|Simulation steps|Wall time|Failure|
|---|---|---:|---:|---:|---:|---|
|6ddc6a1 /8061_0|bowl / spatial task0 init0|0/1|8|217|518.547s|Measured payload collision after publicly verified lift|
|6ddc6a1 /8061_20|box / object task0 init0|0/1|9|137|719.444s|Duplicate destination binding; no remaining public option|
|6ddc6a1 /8061_40|container representative init0|1/1|6|594|272.254s|Native success on release|

Each 0/1 has Wilson95% 0–79.3%; the 1/1 interval is 20.7–100%. These are separate category development probes, not 20/category qualification. Full source-specific rows are in `reports/oracle_closed_progress_20261018.json`; startup rows are excluded.

## Public held-boundary diagnosis

The bowl's first carry blocker is exactly agentview pixel(556,791) in source_step4, inside the current raw SAM mask. It is on the dark bowl silhouette in RGB, 64.927mm from the pre-lift static scene, and 2.544mm from the retained current payload. Its depth component is a singleton, so clean-object filtering removed it. Its Z lies 0.019mm outside the transported surface extent. Current interior neighbours provide both appearance and depth support; the adjacent tabletop has a large depth/colour discontinuity. This correct-frame diagnosis replaces no historical result. `reports/bowl8061_public_blocker_CPU_20261018.json` records the measurements and neighbours; the corresponding RGB crops are retained.

Source 1da79f2 combines the current semantic edge with the existing two-pixel RGB/depth rule and static-scene veto. The semantic mask alone cannot assign membership. Previously supported membership is retained across extent-limited geometric helpers, preventing repeated removal/readdition of the same edge pixels. No collision margin, force, servo tolerance or budget is increased.

The exact saved-public-geometry CPU recheck includes the old blocker with zero residual and passes the same saved screened pose. The adjacent tabletop pixel remains an obstacle (scene residual0, payload distance129.008mm). All retained payload samples are at least63.426mm from the pre-lift static scene. The measured membership/screen portion takes14.093s; this excludes initial imports, robot geometry and base-cloud reconstruction and is not decision-model latency. The discarded first development implementation took259.149s in that portion because of the non-converging edge loop; its report remains. Corrected result: `reports/bowl8061_payload_semantic_edge_converged_static_dev_CPU_20261018.json`. This is CPU planning evidence, not a task-success result.

Final affected CPU set:147 passed in57.83s (`test_bounded_payload.py` and `test_bounded_skills.py`). The new silhouette and convergence cases are included. An earlier24-case subset and147-case runs overlap; counts are not summed. The existing unknown pytest timeout-option warning remains. Ruff baseline/current comparison found one existing CPY001 per changed Python file and zero new findings; diff check passed.

Runtime source1da79f2 was pushed to user-fork/harness-v5. Snapshot: `/public/home/sunyihan/rpent_libero_eval/source_bounded_1da79f2_20261017`; archive SHA256: `d60ac1a0187401a002708e65c9ecae15c9cffe4a5a325e4a238834cc8df1f609`. It uses the same entrypoint/interpreter above. CPU manifest/state preflight passed. Exact-source/launcher startup8068_0 is queued after8065_20 to keep aggregate concurrency at3. Full bowl physical validation remains pending.

Shared spec/schema fields are unchanged. Spec SHA256: `955922e4c05a6f1d309a9846902033ce58b810745088a067ead5d62093eb068e`; schema SHA256: `0da29ae7727d35c91083f3d0d2971cfbc8d91da6214b519c1202f388874d1de5`.

Resources follow the 10/17 override: node02 only, aggregate Codex3 cap3, Nice500. Dependency8064 was removed only after a live query proved two running jobs; the startup then occupied the third slot. Its full continuation replaced the completed startup. No running task, protected c5/c6/rf job or historical held job was cancelled, modified or released. Queue evidence: `reports/resource_latest_node02_cap3_20261018.{json,png}`.
