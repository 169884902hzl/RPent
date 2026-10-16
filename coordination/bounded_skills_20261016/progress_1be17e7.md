# Codex3 — bounded skills progress, 2026-10-16 (source 1be17e7)

Scope: code and simulation development only. No training, no real robot, no c5/c6 or old held job changes. Source pushed to user-fork/harness-v5.

Canonical paths are under /home/agilex/cobot_magic/rpent_libero_eval; model/MuJoCo consumers must reload these exact source bytes:

- `SKILL_PACKAGE_SPEC.md`: SHA256 `3092f22056221c69606462de9acb059dea2e0ffd45aac70ab5381a395a27360a`
- `rpent/skill_package/schema.json`: SHA256 `e4ce602717e25f191863080ee4b2e07d07802c084dbbed3cf26f4b0144cf5f98`
- `rpent/skill_package/contract.py`: SHA256 `4690e01d91ea18b537984feab3fa513a08b974d8f8b98916cfb56d3ce7d9bc18`
- `rpent/skill_package/trajectory.py`: SHA256 `421545fd71e3e6efc265dbd58f39b42aa897d727f82952fed8fc1d71c14ee10d`
- `robots/libero/bounded_motion.py`: SHA256 `ac8862e82a797fe41b24730cb03975846caba53fa842c4c2b401a9eb8310f57a`
- `robots/libero/bounded_skills.py`: SHA256 `bedf308f480ec22d783b195d336e443524a605916e2aabd211ec0ebc6fa81e46`

48 focused CPU checks pass (one existing pytest-timeout configuration warning); includes early interruption, angular braking, current p/v/a/j retargeting, failed brake reporting, transfer-target cross-field validation, oracle ID retention and warm-IK acceptance tolerances. Source6e startup job7543 executes295 physical controls. Request generation dropped344.5→142.5→63.8s, still too slow for online lookahead; these are candidate-generation times, NOT model latency.

**Complete π0.5-only control**: job7528, source84cf146, 220 original development episodes, 215 successful. Per category20: bowl/box/cup/container/microwave open/microwave close/stove on20; drawer open/drawer close/stove off19; plate push18. Exact per-episode records and Wilson intervals are in `/public/home/sunyihan/rpent_libero_eval/results/bounded_skills/reports_20261016/pi05_7528.json`. Full original instruction, 10,000 simulation-step budget, repeated inference until native success/truncation. This is not autonomous skill-package or model success. Plate task is actually push; old registered case names/records retained, report category corrected to plate_push.

**C3 paired motion**, source84cf146:20states×3routes×4methods=240 records, jobs7520/7523–7526. Median actual jerk RMS old move_to9.385, old move9.532, newK1 .881, newK4 .647 m/s³. Median path/chord1.298/1.300/1.283/1.313. K4 endpoint60/60, measured internal stops0. K1 has17/60 routes interrupted by tracking error; do not call all routes passed. Legacy tracking residual is a per-command target residual, unlike new timed-reference residual. Older C2 jobs7514/7516–7519 remain separate. Full recount script `scripts/summarize_bounded_probes.py`.

**Fallback**:7536 did17 realπ0.5 blocks,86controls and native task success; native stop bypassed braking, so it does NOT prove repaired handoff.7541 selected pick/bowl in a drawer-close scene and measured pickup,82controls; its old handoff ran0brake ticks. This is a pickup-only diagnostic, not drawer performance or successful smooth handoff. New source exposes rejected handoff as interrupted, with the original measured-subtask outcome preserved.

**Whole-chain debug**:7538/7539(source823f600) and7544(source6e26831) were deliberately stopped after supported code faults were found; all choices/partial traces and development_stop.json remain. No final task score assigned to these partial runs. Oracle had not retained resolved public IDs; corrected. Near-pi equivalent wrist choice led repeated tracking/collision failures; source1be17e7 uses the lower-turn symmetric contact orientation among near-equal quality candidates, without changing force/budget. Revalidation follows. These development changes are not a claim of skill qualification.

**Historical control**:7540 used actual `/public/home/sunyihan/rpent_libero_eval/source_v5_interim_legal_r2_20261007` plus original job4580 budget:2decisions, official success, full run.140 original40 paired cases now run in7545(array0–3). Its four historical module hashes are recorded per episode. Original90 extension is still missing; must not claim a full11-category historical171 comparison. Old wrapper omitted wall/step fields in its summary; raw legacy_result preserves wall_s. New worker counts both single-control and returned chunk-control calls; no behavior/config changes to historical modules.

**Pending dependencies / work**: request generation remains high; true asynchronous candidate-generation/service/execution wiring, complete category oracle chains, valid non-native fallback handoff, original90 control admission, and same-state oracle/VLA branches. No complete confirmation registry has yet been located: the known665-identity registry explicitly says coverage_complete=false. Codex1: please supply the current complete confirmation/reserved-state registry for branch/history exclusion. Until then no confirmation-derived logs are admitted as fallback history (history n=0/null remains honest); feasibility outputs are training=false. Codex2: reload schema/contract and share the actual bounded-choice service endpoint/client ownership for async integration; current reported K4 cachedP90 .9853s excludes HTTP and candidate generation.

All controls here are explicitly oracle upper-bound / π0.5 comparison / historical expert, not a new Robot Decider model result. vla_task is absent from bounded candidates. No hidden policy or implicit VLA fallback. Old v5 freeze gates retired; new criteria await feasibility evidence.
