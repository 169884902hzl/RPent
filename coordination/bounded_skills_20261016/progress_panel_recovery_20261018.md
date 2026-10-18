# Measured panel direction and screened secondary-axis recovery

Code `ff0038711320c9d04372f1d28026b0e56945792b` is pushed to `user-fork/harness-v5`. A contacted panel now retains the last fresh public normal through occlusion, with its true capture age. It no longer restores the original contact normal. The private oracle tries existing screened axis increments in order of normal magnitude; each must contribute at least 5mm projected progress. Collision screening, robot limits and public candidate construction remain in force.

Saved microwave9018 requests demonstrate both causes. Row3 measured normal was [-0.84697,-0.53164,-0.00097] at capture6. Row4 reverted to [-0.99749,-0.07080,-0.00281]. Keeping the measured normal alone still selected release; changing the selector alone also selected release. Together they select the existing legal y+1cm nudge. This is CPU selector replay, with committed source identity fixed, zero planner calls and zero controls; it does not prove task completion or fresh identity binding.

Private diagnostic labels show the microwave joint advancing from -1.50155 to -0.88971 and then stalling near -0.88136, rather than returning to its initial open position. These labels do not enter public requests.

CPU combined run: 227 passed and 8 failed; all 8 failures were the obsolete judge/6 literal in chunk assertions, while all 207 adapter cases passed. After changing that assertion to judge/7, the entire chunk file passed 28/28 in39.88s. Behavior assertions were retained. `git diff --check` passed. See `reports/panel_recovery_validation_CPU_20261018.json` and `reports/microwave9018_choice_replay_r2_CPU_20261018.json`.

Private judge is `libero-private-task-progress-rules/7`. Wire schema remains `bounded-skills/3`, legality remains `public-request-legal/2`. Schema SHA `df17c6c49e4992247ab8ff37ebf528f893ac6887ea8cf946e25668aca110b4aa`; contract SHA `7e898e3bd4e8f4c7a4e9951d897cc1fe682037ee35ee4d6d5cc1f52606e2f49c`. Codex1/Codex2 can check these exact bytes; no model training is authorized.

Archive SHA `c778d531bbe4d78d9add82978032afc0f6f2b484be1dc60a6a3e1b31e65550c7`. Snapshot `/public/home/sunyihan/rpent_libero_eval/source_bounded_chunk_v3_panel_recovery_20261018_ff00387`; entry `scripts.probe_bounded_feasibility:episode`; interpreter `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`. Physical validation is pending the same-launcher startup and matched boundary-rule pair. No category, freeze or confirmation conclusion follows from these CPU checks.

Development shard9022_120, which still used a5efcd2 and the two proven bugs, was stopped after preserving raw choices/labels and their hashes. It has no completed pair. The separate bowl9022_2 continues: its new-rule arm achieved native success in3decisions/260simulation steps; the legacy arm is still pending completion. Earlier9018 retains its failed new arm and cancelled partial legacy arm. All records remain available.

## Closed bowl pair and resumed oracle cohorts

Bowl9022_2 is now closed: both arms reached native success at260simulation steps, with3/5decisions and356.706/435.904seconds (new/legacy). The source for this pair is a5efcd2; do not relabel it with ff00387. New-rule actions/decision histogram is {3:1,2:1,1:1}, legacy {2:1,1:4}. Lower stopped on measured_sweep_collision before any physical motion, and release later ended at native_success. These stops remain separate in the raw records.

| Arm | Perception s | Planning s | Sim/render s | Oracle exclusive s | Total wall s |
| --- | ---: | ---: | ---: | ---: | ---: |
| New | 152.694 | 175.847 | 6.992 | 3.274 | 356.706 |
| Legacy | 161.794 | 246.685 | 7.134 | 7.693 | 435.904 |

Execution-root perception alone is113.477/94.002seconds, already included above. Each bounded receipt currently calls `MeasuredSkillAdapter.refresh`, which captures RGB-D and passes the full vocabulary to `MeasuredScene.refresh`. A narrower query is technically supported, but refresh also updates obstacle identities, held-surface membership, fixture aliases and scene-change retry eligibility. Substituting cached values would change those public consequences. No selective-refresh performance claim or implementation change is made without an equal-input comparison; full-scene receipt measurements remain active.

Microwave startup9024_120 completed0:0 after305physical steps under ff00387 with the same launcher. That is startup evidence, not a full task score. Full matched microwave pair9025_120 is running. Oracle-only original20 array9026 covers180states from9categories: bowl, historical can/box_transfer, container, cup, drawer close/open, plate_push, stove off/on. It uses this same source, launcher and startup proof with pi0.5 disabled. Microwave categories remain separate pending the representative repair. These are development cohorts, never confirmation or training data. GPU jobs are node02/nice500; a returning Codex2 job reduces future aggregate concurrency to3 without cancelling running tasks.
