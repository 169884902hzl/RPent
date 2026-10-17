# Anchored nudge progress and physical contact diagnosis

Development only: original scenes, no training/PRO input/confirmation re-scoring. The retired v5 confirmation thresholds are not reused as qualification.

Runtime96679adaa8449b9d607dba2da435a56ca2e86db4 is pushed to user-fork/harness-v5. Snapshot /public/home/sunyihan/rpent_libero_eval/source_bounded_96679ad_20261017; archive SHA256 bcb059c52d9c77fed932e17af6e55b1fa4eff10e0f0f1e19906dd87352b0c483. Spec SHA2566fd572205594fd403bef341ce41cd580ca34611ec3f262b64cb081c2437cc463; schema unchanged0da29ae7727d35c91083f3d0d2971cfbc8d91da6214b519c1202f388874d1de5. Entry scripts.probe_bounded_feasibility:episode, interpreter /public/home/sunyihan/rpent_libero_eval/.venv/bin/python.

## Measured bug and change

The old anchored-nudge receipt checked the norm of a segmented entity's centre displacement. It could verify a push when that centre drifted opposite to the commanded axis. The new check retains the full displacement, records command_axis and axis_progress_m in execution diagnostics, and requires5mm progress along the command. At least5mm in the opposite direction returns failure/contact_failure/contact_motion_opposes_command; smaller forward progress returns no_effect/contact_no_measured_progress. Missing/stale measurements remain unmeasured. Native success has precedence. Only public measurements and selected parameters are used; requests/schema gain no fields. Generic failure-memory handling counts the new failure normally.

CPU tests138 passed,1 existing timeout-option warning,62.69s; scoped Ruff(--ignore CPY001) and diff check pass. New regression cases distinguish commanded,opposite,perpendicular,stationary,occluded and stale object measurements.

## Full old-plate diagnosis

Old source2da8248/job8036_160 closed native failure0/1 (Wilson95%0–79.3%),160 decisions,4834 controls,9656.206s. Steps by skill:move_to1780,align72,descend532,set_gripper420,nudge1708,observe322. The decision budget ended first. All original receipts,actions and the task score remain unchanged.

This source had no saved full controller snapshots. An isolated CPU replay starts from the exact official state SHA cea30572c1ece1c5d5a53c64fef51544c3a02dbb6bf6bc06d02d3a03ea719aa7,uses the same reset seed and15 initial open-gripper controls,then replays all4834 recorded controls. Initial EEF residual0;maximum EEF residual4.94548e-9m. This is measured replay agreement,not a claim of full snapshot identity or a new task result. Private contact/COM values only annotate the recorded controls.

Of104 nudge attempts,100 have no finger contact. Four original success receipts all correspond to true object motion below5mm. The new signed-axis rule rejects2 of these as opposite-direction failure;2 remain false positives from same-direction segmentation drift. This fix reduces a demonstrated receipt error but does not solve contact or the remaining measurement ambiguity. The original4 successes are not overwritten. On the first such pair, true displacement was0.0289mm; the next had no finger contact and effectively zero object motion.

Evidence: reports/plate8036_direction_recount_CPU_20261018.json (per-decision pairs and input hashes), plus private full/prefix CPU ledgers under the same reports directory on5880. A first recount failed to serialize a NumPy int64 aggregate; explicit integer conversion fixed the derived-report writer. No physical run was repeated for that formatting fix.

## Contact-route development and resources

On the same saved public RGB-D and static Panda meshes,192 thin-rim approach candidates were screened across8 measured perimeter patches,6 tilt angles and4 yaw orientations. Routes retain existing swept collision/IK/closure checks. Some oblique contacts on different measured rim patches pass; the attempted oblique contacts at the originally selected patch all collide. No oblique planner change is merged. CPU-only physical diagnostic8089 completed four same-state routes with no GPU or private motion-selection inputs. Existing top contact moved0.685mm;patch6/tilt15 was blocked before pushing;patch6/tilt45 moved0.00104mm;patch7/tilt15/yaw90 moved6.211mm before a later sweep was rejected. That last push was toward the measured centre,not a task-goal completion. The frozen initial public scene is a limitation: this is a contact diagnostic,not a live-perception task upper bound. Raw per-control paths/hashes and each rejection are in reports/plate8036_public_contact_cpu_physics_20261018.json. No oblique planner change is merged.

Same-source/launcher startup8086_160 completed336 actual controls in119.156s,exit0. This is startup evidence,not task success. Current-source first20/category bowl oracle array8087_0-19%1 is submitted;pi05 disabled,all failures retained. Other GPU lanes are730e859 microwave_close8085_120 and845a720 representatives8072%1. node02 only,Nice500,total GPU cap3; no node01/protected/old-held job modified. Source730e859 startup8084 completed350 controls before full8085 admission. Source845a720 stove_off8075_180 succeeded1/1 in4 decisions,456 controls,205.553s;microwave_open8075_140 failed0/1 in16 decisions,645 controls,1073.372s. Different source/state repeats are never pooled as independent trials.

No current-source20/category results yet; no freeze claim. Continue oracle feasibility before new comparator,K1/K4 task and fork runs. Actual model HTTP async evidence still needs Codex2's caller-owned endpoint/latency. VLA history remainsn0/null while exhaustive history-exclusion admission is unavailable.
