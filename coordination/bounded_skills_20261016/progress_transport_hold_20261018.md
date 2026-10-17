# Transport hold loss: public receipts and recovery

Original-scene simulation development only. No training, PRO input, confirmation re-scoring or category qualification. Permanent confirmation exclusions remain in force.

Runtime source `f64a5c4166348da72cf2f0a623bc317067c8a62e`, pushed to `user-fork/harness-v5`; snapshot `/public/home/sunyihan/rpent_libero_eval/source_bounded_f64a5c4_20261017`. Archive SHA256 `6734b3e05e3893223ede16ef268d38bf6b955f6bf095b78caf7655021b2ece9e`. Entrypoint `scripts.probe_bounded_feasibility:episode`; interpreter `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`.

## Closed physical result and root cause

Source845a720, box8071_20: native task failure0/1,14 decisions,813 simulation controls,572.923s,pi05_calls0. Wilson95%0–79.3%. Lift verified on the second attempt; held alignment executed92 controls, then carry192. The box fell during carry, but the old attachment flag remained set, so subsequent lower/scan options were blocked by an obsolete payload collision. This result remains unchanged.

The saved endpoint snapshots independently show double-finger contact after lift and alignment, and no finger contact plus floor support after carry. The public post-carry image shows empty jaws and the box near its original support. Private snapshot metrology is diagnostic only. Full flat-state restoration error0; cached EEF sensor residuals remain recorded.

A CPU replay of the192 saved carry controls loses double-finger contact at control index54; the first non-gripper contact at index60 is the floor. The original recorded aperture decreases from48.215mm before carry to below5mm at index60; every recorded gripper command remains close(+1), so an accidental release command is excluded. Replay maximum EEF residual is0.24534mm: this is approximate contact diagnosis, not exact physical re-execution or a new success label. No scene collision precedes loss in this replay. A deeper/stabler contact needs further physical development; this receipt fix alone does not prevent the drop. Six saved public candidates were re-screened with the production smooth-route and closure checks: the selected0.686 normal-quality contact passed, but all five stronger0.914–0.945 alternatives failed route or closure collision. Merely sorting stronger contacts first is therefore unsupported by this case; no ranking or collision-margin change was merged. See reports/box8071_opposition_routes_public_CPU_20261018.json.

## Public behavior change

Fresh visible RGB-D bounds are transported by the measured before/after EEF rigid transform and compared at a motion or blended-chunk endpoint. An extent separation above the existing15mm coupling tolerance yields `failure/contact_failure/public_hold_lost`, `changes[].held=false`, and clears the stale attachment, contact and grasp references. Occluded/stale measurements do not assert loss; rotation is accounted for. Native task success keeps precedence. Loss stops a selected chunk before its remaining contact suffix. This uses public sensor geometry only, with no private contact or coordinate in requests/options/receipts.

Single-action saved-data CPU comparison: alignment row7→8 gap0,loss=false; carry row8→9 gap370.998mm,loss=true. It does not continuously observe the transport interior. Reports: [public replay](reports/box8071_public_hold_loss_replay_CPU_20261018.json), [private snapshot metrology](reports/box8071_private_hold_snapshot_CPU_20261018.json), [private carry contact replay](reports/box8071_carry_contact_replay_private_CPU_20261018.json).

CPU validation:134 passed,1 existing pytest configuration warning,in65.08s in `test_bounded_skills.py`; scoped Ruff ignoring existingCPY001 and diff check pass. Includes attached,dropped,occluded,stale cases for both single and blended motion, wrist rotation, and not executing a remaining release after observed loss. The first added blended test incorrectly requested an align option while held; it failed4 cases with StopIteration, then was corrected to use two offered carry options. No production assertion was weakened.

Shared schema bytes unchanged SHA256 `0da29ae7727d35c91083f3d0d2971cfbc8d91da6214b519c1202f388874d1de5`. Spec semantics updated, SHA256 `c30aaac83d3ceecdbc470044d242b28e013b122053073bf6b48698eb0adb41c6`. Codex1/Codex2 must use this source/spec for the changed hold-loss receipt behavior.

## Physical checks and resources

CPU manifest/state preflight passed. Same-source/launcher startup8081_20 waits after the entire8075 serial channel. It has not yet executed; do not count it as task or physical evidence. The earlier fab743b startup8079_20 was verified PENDING and cancelled as superseded; it had no physical result. Submission identities/hashes are in reports/transport_hold_f64a5c4_submission_20261018.json.

Latest source845a720 microwave_close8075_120 also closed failure0/1,12 decisions,444 controls,878.588s (Wilson95%0–79.3%): three successful measured nudges, then contact measurement lost and recovery collision. Original receipts retained.

Active channels: old plate8036_160,representatives8072%1,and fixture8075%1; startup8081 follows8075. Only node02,Nice500,total maximum3. No running job,old held job or protected c5/c6/rf job modified. The current source still has no20/category upper-bound cohort. Comparator/K1-K4 task/fork priority follows oracle feasibility. Actual model endpoint/server latency and eligible VLA-history provenance are still unavailable; history remainsn0/null.
