# Public contact-surface motion, development delivery

No training, PRO input or confirmation rescoring. Runtime source `1fde9950911d28fd4de6c9c83ff925d56fd4e0f7` is pushed to `user-fork/harness-v5`. Snapshot `/public/home/sunyihan/rpent_libero_eval/source_bounded_1fde995_20261017`; archive SHA256 `52486f0a472d6470419f6fd6c12dd7f8037f6b1ff4cd5eccca74c30dc0a9b088`. Entry `scripts.probe_bounded_feasibility:episode`, interpreter `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`.

Canonical spec SHA256 `693d3b784fdaa53750ac6aa5401b385bab2e509f813670eeca55abc25fc71d34`; schema bytes unchanged, SHA256 `0da29ae7727d35c91083f3d0d2971cfbc8d91da6214b519c1202f388874d1de5`. Codex2 should use this spec/source. Requests gain no fields; nudge receipt semantics change as follows.

## Cause and repair

An entity centre can move because its visible segmented surface changes. A signed centre check still verified two stationary plate pushes. Contact verification now fits the pre-action public surface along both signs of the commanded axis to current robot-filtered depth. Fixture verification uses current measured handle pixels, avoiding the stationary parent cabinet. No hand displacement, task goal or simulator pose guides the fit. Capped residual8mm, minimum40 samples/50% overlap and a1mm grid reuse bounded public geometry scales. Fits within an additional(1mm)^2 mean squared residual remain compatible. This is a geometric ambiguity range,not a statistical interval. Only a range wholly beyond5mm in the commanded direction verifies progress; wholly opposite gives failure,wholly within+/-5mm gives no_effect; missing,weak,boundary or mixed fits stay unmeasured. Native success wins. The original entity displacement remains diagnostic. Reference clouds are now saved alongside existing public geometry.

206 CPU tests passed in70.98s with1 existing timeout-option warning. Scoped Ruff(--ignore CPY001) and diff checks passed. Regressions cover stationary/moving/opposite/perpendicular surfaces,segmentation-centre drift,stale/occluded evidence,planar ambiguity and a moving handle beside a stationary parent. CPU checks do not establish physical task success.

## Saved-data pairs

Production fitting function SHA matches the committed module. In15 selected saved-public examples: all4 old plate false successes cease to be success(3 no_effect,1 unmeasured);9 true drawer movements remain success;2 stationary drawer pushes become no_effect. Diagnostic inputs use the saved voxel scene union rather than the full live raw scene; therefore this is a counterfactual evidence check,not a whole-rollout result or validation accuracy estimate. The private plate/control replay and drawer joint replay label results only after public predictions. Original actions,receipts and native scores stay unchanged. Per-example evidence/hashes: `reports/bounded_axis_fit_pairs_CPU_20261018.json`.

## Physical progress and resource use

Preceding source845a720 drawer_close8072_80 completed native success1/1(Wilson95%20.7–100%),30 decisions,1455 controls,2395.996s. The private CPU prefix shows the first8 pushes advance8–9mm each,and2 later success receipts occur without joint motion; those are the above regression examples. Preceding730e859 microwave_close8085_120 failed0/1(Wilson0–79.3%),13 decisions,513 controls,1030.393s. Release/withdrawal is improved,but closing still stops short and public options run out; retained as failure. Current96679ad bowl array8087 completed initial2/2,not yet20/category. Different source/state repeats are never pooled as independent samples.

After absolute-path/state CPU preflight,startup8098_80 is queued after8072. Only unstarted8072_160/200 were cancelled to replace old contact probes;8072_100 continues naturally. Full new-source arrays will be admitted only after the same-source/launcher startup executes controls. Remaining GPU lanes are8087 and8095;all node02,Nice500,aggregate<=3. No protected job,node01 job or old held job changed. A CPU-only drawer diagnostic8091 failed because login-node/tmp was not shared;moving the script to preparation fixed8092,which completed in18s with no GPU. Raw startup failure remains.

No current-source20/category result or freeze. Continue oracle-only upper bounds first. Contact stability,plate routing,box transport loss and microwave closing remain development work;no oblique contact planner is merged. Actual model HTTP async still needs the caller-owned endpoint/latency;VLA history remainsn0/null while exhaustive history admission is unavailable.
