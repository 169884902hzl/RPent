# Current-contact withdrawal repair

Original-scene CPU/simulation development only; no training, PRO input, confirmation re-scoring or qualification. Confirmation exclusions remain permanent.

Runtime commit730e859 on user-fork/harness-v5. Snapshot: /public/home/sunyihan/rpent_libero_eval/source_bounded_730e859_20261017. Archive SHA256 a0a713153bf418120b0f53a76d4b76809be5757a9b96b9e21434e7e22c41e258. Spec SHA256 01dff380fb0ab31ffc1132e898af441cf86542b6900bd87efeabf1015368498f. Schema bytes unchanged, SHA256 0da29ae7727d35c91083f3d0d2971cfbc8d91da6214b519c1202f388874d1de5. Entrypoint scripts.probe_bounded_feasibility:episode; interpreter /public/home/sunyihan/rpent_libero_eval/.venv/bin/python.

## Physical finding

Source845a720 microwave_close8075_120 closed0/1:12 decisions,444 controls,878.588s; Wilson95%0–79.3%,pi05_calls0. The private snapshot joint moved from-1.50155 to-0.81690rad but did not close. Public receipts recorded three measured nudges, followed by lost contact measurement. After gripper opening, the door entity disappeared from segmentation; five current depth points then blocked every withdrawal route. The old withdrawal record referred to the initial precontact surface rather than the moved surface. Private joint/snapshot metrology stays diagnostic and never supplies runtime options or coordinates.

Before opening, the adapter now copies the latest public contact cloud. After opening, matching current self-filtered RGB-D may retain its identity even without SAM. Stored points are neither subtracted directly nor translated with the departing EEF. Existing1mm surface residual, measured extent, depth continuity and swept collision limits remain. The repair does not claim that the fixture was opened/closed or attached to the hand.

## CPU evidence

The changed production _contact_pixels method was replayed on saved public8075 RGB-D. All five blocking samples had distance0 to recovered current target pixels. SmoothMotion.prepare accepted +z,-x,-y4cm withdrawal routes and continued rejecting+x,+y as collisions. This is route feasibility on saved data, not physical task completion. Report: reports/microwave8075_production_withdrawal_public_CPU_20261018.json; its module SHA matches the submitted source. Current pixels include361242 raw samples before voxelisation; this count is not comparable to the20322 voxelised reference samples.

Tests: .venv/bin/python -m pytest tests/unit_tests/robots/libero/test_bounded_skills.py -q:136 passed,1 existing timeout-option warning,64.02s. New cases cover missing SAM after release, copying the latest surface, hand movement without surface attachment,6mm adjacent depth rejection,and rejection after the surface moves3cm. The first test run exposed metadata source overwritten by the lower-level evidence dictionary; dictionary ordering was corrected and the whole file rerun. Scoped Ruff(--ignore CPY001) and git diff --check passed.

The first saved-data replay used a nonexistent row geometry key to obtain a capture tag and raised KeyError; it was corrected to use the actual saved world filename capture index,then rerun. No physical record or score was changed.

## Queue and remaining work

CPU manifest/state preflight passed. Same-source/launcher startup8084_120 is queued after8036_160, taking over that serial lane. It has not produced a physical request yet. Other lanes remain8072%1 and8075%1 followed by8081_20. All are node02,Nice500; combined maximum3. No running/protected/old-held job was changed. No additional full-source arrays will count as admitted before same-launcher physical startup.

Closed source845a720 representatives: bowl1/1,container1/1,cup1/1,box0/1,microwave_close0/1; the two-cup case used15 decisions,1883 controls,1194.383s. Different source repeats of the same state remain separate,not independent trials. Current-source20/category results remain missing. Real model HTTP async still lacks the caller-owned endpoint/latency; VLA history remainsn0/null while exhaustive confirmation-history admission is unavailable. Continue oracle feasibility before further controls,K1/K4 task checks,and forks.
