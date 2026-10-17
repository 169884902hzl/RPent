# Codex3: precontact panel identity and rotary frame repair

Original LIBERO development only; pi0.5 disabled in every oracle run below. No training, PRO access, confirmation rescoring, node01 submission or protected-job changes. Shared spec/schema are unchanged.

## Current resource allocation

Only node02, Nice500, aggregate cap3. Three serial channels:8036 plate then8038 double-cup startup;8043 microwave full after successful8042 startup;8044 rotary startup after8040. Arrays use throttle1 except8046 stove_off,now throttle2;the concurrent plate->cup channel keeps the aggregate cap3. Resource evidence: `reports/resource_latest_node02_cap3_20261018.{json,png}`. The latest live allocation at12:15 PDT isnode02=3,node01=0;the captured resource report records its own exact timestamp. Historical held jobs remain held.

## Precontact panel identity

Commit `cbaa92ac033f323bce3b088f50b07668351962e4`, pushed to user-fork/harness-v5. Snapshot `/public/home/sunyihan/rpent_libero_eval/source_bounded_cbaa92a_20261017`; archive SHA256 `12231cb4b1473837643643083cc19dcaec9082ccb3a0a43a5793cda374531cdf`.

8037_120 failed0/1,6decisions,355controls,484.7s. Four old blocking door-edge pixels were part of the original measured door, but vanished from the partial post-approach part mask. Exact private static-fixture restoration independently identified the same door edge; private geometry was diagnostic only. Runtime repair uses current self-filtered RGB-D connected components supported by the original measured surface, restricted to its original extent, only while precontact/open and the anchor remains within1cm. A moved surface and a depth-disconnected neighbour stay excluded.

Full same-public-input descending route:baseline fails measured_sweep_collision;repair passes the same hand-mesh/IK screen. The diagnostic uses the saved public screen target as the reference sample, whereas runtime retains raw instance pixels; this distinction remains recorded. CPU planning evidence is not task success. `reports/microwave8037_whole_descend_CPU_20261018.json`.

Checks:117 passed,45.13s, one existing unknown-timeout-option warning. Scoped Ruff passes with only pre-existing missing-copyright CPY001 excluded;diff check passes.8042 startup uses this exact source/launcher and executes350controls;status startup_physical,not a task-score row.8043 is the corresponding full physical run:failure0/1,12decisions,444controls,868.5s. It clears the original descent blockage,then three measured push-progress receipts and one missing measurement precede release/withdrawal collision. The task is not fixed.

## Private oracle rotary sign

Commit `2ceec13` transforms the oracle's outward rotary direction into rotate_wrist's actual local-z convention using the measured control normal and public hand quaternion. Public skill, schema, control limits and collision margins are unchanged.

8040_180 fails0/1,10decisions,577controls,418.9s. Exact complete-state CPU control replay shows two old -45degree choices increase the stove joint0.984->1.718->2.100. Contact is present throughout both turns;this is not merely a missing contact. From the same saved closed-gripper state, newly generated/public-screened branches give:-45degree0.984->1.717,+45degree0.984->0.196. Both93controls,endpoint reached. One+45degree does not yet satisfy task success;no successful full episode is claimed. Private joint/contact labels are isolated from runtime inputs. Raw reports and SHA256 are referenced in `reports/stove8040_contacts_CPU_20261018_summary.json` and `reports/stove8040_direction_branch_CPU_20261018_summary.json`.

15 oracle-related CPU tests passed,9.01s,one existing warning;scoped Ruff/diff check pass. Snapshot `/public/home/sunyihan/rpent_libero_eval/source_bounded_2ceec13_20261017`;archive SHA256 `2f473349ee9e0e20e16a7ffc11db5c4004f863bc0e74889603b5f90cb7f5446e`.8044 physical startup completed309controls with a verified marker.8045_180 full oracleK4 succeeds1/1,4decisions,456controls,204.5s,pi0.5calls0.8046 continues distinctinit1-19 on exactly this source. Its first completed row,init1,fails0/1,9decisions,548controls,399.9s;the post-turn collision and all receipts remain. These are development rows,not a confirmation or20/category admission.

8040_200(stove_on) independently fails0/1,6decisions,681controls,300.6s. The initial approach reaches its waypoint;descent deviates30mm while measured joint4 reaches approximately-3.070rad, then the braking route is rejected. This is a separate approach/servo issue,not evidence about the new rotary sign. It remains in the ledger.

## Recount and remaining feasibility

ca4ce83 drawer_open is3/4(init0,1,3 successful;init2 failed),Wilson95%30.1-95.4%. Init2 has7 bounded pull nudges then releases and cannot find a clear scan/recovery. Old source-specific rows and repeatedinit0 remain separate. `reports/oracle_closed_progress_20261018.json` records source cohorts,raw episode hashes,counts,Wilson intervals,decisions,steps,wall clock and failure phases. New runs have not yet completed20/category;no expansion to100/category or feasibility admission is claimed.

Plate8036 is from a source predating complete private decision snapshots. An attempted exact private replay was stopped at the missing-snapshot check;no contact diagnosis from an inexact furniture replay is used. Saved public RGB-D/hand geometry can still be analysed. Task-level K1/K4 and new forks follow oracle repairs;historical215/220 pi0.5 and197/220 legacy-expert controls remain historical controls,not bounded-oracle success.

Entrypoint `scripts.probe_bounded_feasibility:episode`;interpreter `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`. No actual model HTTP endpoint/latency evidence has been supplied in this thread;synthetic delays remain labelled synthetic. DevelopmentHistory staysn=0/null pending admissible development-only provenance.

## Withdrawal work in progress

A partial descent near a measured static joint limit must retain the selected measured contact identity for a screened withdrawal,without claiming a held object. A newly opened gripper similarly releases attachment while retaining its previously measured surface solely for withdrawal. CPU regression checks cover the retention,near-limit alternative posture and side scan behavior;the final focused adapter/payload suite passed139tests in53.15s. Scoped Ruff excludes only the existingCPY001 findings;diff check passes. No force,budget,IK,collision or12mm endpoint criterion is relaxed. CPU-only exact-physics restoration of8040_200 matches the entire flattened sim state withmaxerror0. Regenerating public observations differs from the recorded post-control sample by0.138mm EEF and0.000667rad joint;the diagnostic therefore replays the recorded initial public sensor and its final4control samples,with subsequent sensors supplied by the physical simulation. Earlier static-pose-only route checks omit inherited derivatives and are not an equivalent runtime replay.

## a8238d0 symmetric contact ranking and withdrawal identity

Source `a8238d0` is committed and pushed to user-fork/harness-v5. Snapshot `/public/home/sunyihan/rpent_libero_eval/source_bounded_a8238d0_20261017`;archive SHA256 `4118b107d877c490bfaa3697ae6bae20d71bf85cf3f52b5d969f2e9c5b0c3967`. Startup8051_200 uses the same source/launcher as its eventual full stove_on run;it is queued behind8046_183.8046 has been reduced back to throttle1,so its existing two running children drain naturally and the new channel cannot exceed aggregate3.

The fixture planner compares the two parallel-finger symmetric wrist poses at the first viable handle roll. It screens each complete route,then ranks by contact-point joint-limit margin (route minimum breaks ties). This margin is numerical planning evidence,not a servo convergence guarantee. Same8040_200 saved public inputs selectoption6 rather than0: contact margin0.12246 versus0.09790rad. Exact full-physics CPU branches with the original duplicated align prefix yieldoption0 braking rejection at30.37mm versusoption6 endpoint error5.3895mm (568prefix+38descent controls);the latter clears the12mm arrival criterion but is not a completed stove task. No private coordinate chooses either route.

The earlier static screen omitted inherited motion and suggested possible withdrawal. Repeating with the exact saved physics,recorded initial public sensor and final4control samples rejectsall5withdrawal routes,with or without retained identity. This is a negative result,not a working recovery. The new code instead attempts to prevent the bad initial posture and retains identity for other screened recoveries;the full physical startup/episode remains necessary. Raw replay files stay on5880;hash references and limitations are in the accompanying CPU summary.

## 627c861 contact-failure reactivation

The plate8036 ledger shows repeated no_effect contact with source displacement below5mm,while the table centre alone shifts11.8–37.3mm as its visible mask changes. Global scene reset re-enabled the same action (maximum consecutive repetition10 in the partial record). Shared FailureMemory.tick now accepts optional changed_anchors:known anchored contact_no_measured_progress/contact_motion_unmeasured failures persist across unrelated changes and reset after their own source changes. Other failures,including collision routes,retain any-scene-change reset. Callers omitting the optional argument keep the prior behavior. Schema fields are unchanged;spec SHA256 is now `955922e4c05a6f1d309a9846902033ce58b810745088a067ead5d62093eb068e`. Codex2 must sync the canonical shared helper/spec;no training has started.

140 focused adapter,trajectory and schema tests pass52.28s;one existing unknown-timeout-option warning. Scoped Ruff (existingCPY001 excluded) and diff check pass. The companion private-oracle329b4e7 chooses the existing open-gripper option if the required rotary route is blocked,instead of scanning a closed contact.6 focused rotary/fixture selector tests pass4.57s. Neither change yet has a complete task result.

Latest source627c861 snapshot: `/public/home/sunyihan/rpent_libero_eval/source_bounded_627c861_20261017`;archive SHA256 `75710ec5298ab1de2d36f9f4fc3c2321bb4f51df6b6697a3ec6f97787661d95f`. CPU full-manifest/state preflight passes;startup8054_181 is queued behind complete stove_on8053_200.8051_200 actual startup validates606controls with all3receipts successful;the startup status itself is not a task result. The initial full8053 uses exactlya8238d0,not the later627c861 source.

2ceec13 stove_off cohort currently2/5 (init0and2 succeed;1,3,4fail),Wilson95%11.8–76.9%. It remains below the illustrative80%development target and no100/category expansion is allowed. Remaining15registered states are still running serially. New-source recovery replays are a separate cohort;no closed failure is overwritten.
