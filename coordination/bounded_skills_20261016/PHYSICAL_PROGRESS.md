# 10/16 bounded-skills physical development results

Current development and source-specific results are in [native-stop and recovery progress](progress_native_stop_and_recovery_20261018.md), with earlier [panel/rotary diagnostics](progress_panel_and_rotary_frames_20261018.md) retained. Latest runtime source is 1da79f2; the nested-target and moving-silhouette repairs, CPU replays and pending physical checks are described in [target and payload progress](progress_nested_target_and_payload_20261018.md). The full a8238d0 stove_on run succeeds1/1;the627c861 stove_off recovery replay succeeds1/1 on an initial state that failed under2ceec13. These are separate source cohorts, not independent confirmation trials. No current source has completed20/category qualification. All runs below are simulation only,training=false;confirmation labels stay unchanged. The historical motion/control comparisons and earlier be5d8f9 development are retained below.

## Paired waypoint sequences

20 original states x 3 fixed routes x 4 methods; n=60 per method. All attempted routes retained. Stops are measured troughs below5mm/s at intermediate waypoints; commanded stops remain separate.

|Method|Endpoint-complete routes|Jerk RMS median (m/s^3)|Path/chord median|Measured internal stops median|Max tracking residual median (m)|
|---|---:|---:|---:|---:|---:|
|legacy_move_to|60/60|9.3852|1.2981|0.0|0.03532|
|legacy_move|60/60|9.5318|1.2999|0.0|0.03573|
|smooth_k1|40/60|0.8783|1.2979|1.0|0.02501|
|smooth_k4|60/60|0.6467|1.3134|0.0|0.02042|

The old residual is distance to a per-command target; the new residual is distance to a timed trajectory reference. These residuals are not a same-definition comparison. Current b190f44/job7583 K1 includes20 failed routes; its lower path ratio is not evidence that those routes completed. Old commands stop at each segment but no5mm/s trough was measured on these particular legacy routes.

## Full-instruction pi0.5 control

Job7528;source84cf146;220 registered original episodes,215 native successes. Every failure remains, each at10,000 simulation steps. Decisions in this arm count VLA inference blocks, not skill selections. Native-success is private diagnostic scoring, not a model-visible option.

|Category|Success/n|Wilson95%|Inference blocks median/P90|Simulation steps median/P90|
|---|---:|---:|---:|---:|
|bowl_transfer|20/20|83.9–100.0%|15.5/16.1|75.5/80.2|
|box_transfer|20/20|83.9–100.0%|29.0/37.70000000000001|143.5/187.60000000000005|
|container|20/20|83.9–100.0%|24.0/25.0|117.0/122.2|
|cup_transfer|20/20|83.9–100.0%|47.5/53.300000000000004|237.0/266.5|
|drawer_close|19/20|76.4–99.1%|12.0/13.100000000000001|58.5/65.2|
|drawer_open|19/20|76.4–99.1%|26.0/62.00000000000013|126.0/308.0000000000006|
|microwave_close|20/20|83.9–100.0%|39.5/44.100000000000016|195.5/219.30000000000007|
|microwave_open|20/20|83.9–100.0%|26.0/30.50000000000002|129.5/152.4000000000001|
|plate_push|18/20|69.9–97.2%|26.5/245.00000000000279|129.5/1221.4000000000137|
|stove_off|19/20|76.4–99.1%|32.5/337.4000000000003|160.0/1686.1000000000015|
|stove_on|20/20|83.9–100.0%|15.0/16.1|72.5/79.5|

The plate original sentence is a push task; it is reported as plate_push, not plate grab/place. No registered task/state was replaced after results. Oracle K1/K4, historical171 comparator, non-native VLA handoff, true model async trace and same-state self/VLA branches remain separate pending evidence; the215/220 control is not their result.

A later CPU recount uses distance to the same prescribed waypoint polyline for all four controllers. It retains all60 routes per controller,including20 incomplete K1 routes;these geometry errors are separate from the different timed/per-command residuals above.

|Method|Max path deviation median/P90 (mm)|Final endpoint error median/P90 (mm)|Commanded internal stops median|
|---|---:|---:|---:|
|legacy_move_to|20.16 /30.35|10.87 /11.40|2|
|legacy_move|20.49 /30.68|11.26 /11.86|2|
|smooth_k1|6.42 /22.90|6.42 /19.41|2|
|smooth_k4|13.24 /16.71|3.67 /4.82|0|

These are historical b190f44/job7583 motion diagnostics,not the current-source task trials. Recount command: `PYTHONPATH=source_bounded_6ddc6a1_20261017 .venv/bin/python -m scripts.summarize_bounded_probes motion --input results/bounded_skills/motion_20261016/job7583/summary.json --output coordination/bounded_skills_20261016/reports/motion_b190f44_job7583_common_path_20261018.json` from the5880 root. The raw motion records and earlier derived reports are preserved.

Raw/derived evidence:reports/motion_c2.json,reports/motion_b190f44_job7583.json,reports/motion_b190f44_job7583_common_path_20261018.json,reports/pi05_7528.json. Each contains hashed input ledgers and per-state records. Reports are exploratory development, not frozen confirmation.


## Historical expert control completed

Same220 registered original states;197 native successes. Original40 historical no-vla_task family132/140. The90-task diagnostic arm explicitly adapts historical admission/env_meta only,65/80; it is not evidence that the historical171/200 configuration originally supportedLIBERO-90. Physical policy and source hashes are retained per row in reports/legacy220.json. The source is source_v5_interim_legal_r2_20261007. Repeated references to one saved result are deduplicated only after verifying success/decision consistency; duplicate references and infrastructure records remain in the report.

|Category|Historical expert success/n|Wilson95%|Decisions median/P90|
|---|---:|---:|---:|
|bowl_transfer|20/20|83.9–100.0%|2/2|
|box_transfer|19/20|76.4–99.1%|2/3.4|
|container|17/20|64.0–94.8%|2/29.5|
|cup_transfer|20/20|83.9–100.0%|4/4|
|drawer_open|19/20|76.4–99.1%|1/1|
|plate_push|17/20|64.0–94.8%|2/20.7|
|stove_on|20/20|83.9–100.0%|1/1|
|drawer_close|20/20|83.9–100.0%|1/1|
|microwave_close|17/20|64.0–94.8%|1/21|
|microwave_open|10/20|29.9–70.1%|7.5/10.2|
|stove_off|18/20|69.9–97.2%|3/8.4|

Paired with the same-state pi0.5-only control:192 both succeed,23 onlypi0.5 succeeds,5 onlyhistorical expert succeeds,0 both fail. Decision counts differ in meaning:expert skill choices versuspi0.5 inference blocks. reports/legacy220_pi05_paired.json retains each pair. Neither result is the bounded package's upper bound.

## Bounded oracle development gaps

Source7bbb32e/job7589:eleven representative category states,oracleK4,0/11 task successes. All raw failures remain. These are one-state diagnostics, not20/category qualification. Missing mug aliases are fixeda2a6edf. Cached destination options were fixed3a61b37. The604bf07 bowl rechecks7602/7603 both publicly verified grasp/lift, then failed carry because a disconnected tabletop patch in the object's SAM mask was treated as payload.20c3111 keeps only the depth component supported by the current held-object measurement, preserving rejected table points as scene obstacles; related CPU32 passed, physical replacement pending. It also records pre-execution boundary/perception evidence with the actual request instead of the later refreshed state. Furniture representative checks continue with existing public measurement flags enabled; no missing handle pose is invented.

## Same-snapshot fork

Source7bbb32e/job7588 completed one original bowl pair from one hashed full snapshot. Self branch:task failure,public held-pick=true,private sustained-grasp v3=null. VLA branch:task native success,public held-pick=false,private sustained-grasp v3=false. Native task completion after VLA is not a successful held-pick label. Raw pair and both outcomes remain in results/bounded_skills/forks_20261016/job7588/bowl_transfer_libero_spatial_t0_s0/pair.json. This is one diagnostic pair,training=false; no conditional-training claim follows.

Real model/HTTP async evidence still needs a caller-owned endpoint fromCodex2. Conservative stale-request rejection currently prevents claiming useful continuation overlap. VLA history staysn=0/null while exhaustive confirmation-history admission evidence is unavailable. Current known registry checks2165 identities and4 typed reservations withcoverage_complete=false; all confirmation exclusions remain permanent.


## be5d8f9: measured membership and fixture orientation repairs

CPU/simulation development only. Source snapshot `/public/home/sunyihan/rpent_libero_eval/source_bounded_be5d8f9_20261016`; archive SHA256 `ceb2868071a325a2331fe2ecb1729b7a9d5888da1ebc849034e5f0fb0de0aed8`. Canonical schema/contract/trajectory remain unchanged from the b190f44 delivery. New focused CPU tests:48 passed (bounded_skills, v5_grasp_route, v5_grasp_geometry, bounded_screen). Separate probe resilience set:39 passed including the new no-opposition early rejection. These counts overlap and must not be added.

The 58effc3 bowl K1 reached publicly verified lift; carry still collided at a wrist pixel 0.660mm from an agentview target pixel. The cup similarly collided at0.219mm. CPU replay of the exact saved public RGB-D found the missing wrist pixels2–3 pixels beyond the mask, so one-ring cross-view completion could not associate them.92a2298 requires every additional pixel to have independent opposite-view mask/depth evidence and a continuous same-view surface path; it keeps the existing3mm spatial/1mm depth limits. Exact residual membership changes false→true in both captures; this is CPU membership evidence, not task success. Inputs and hashes:reports/surface_membership_7638_7640_CPU.json. Neighbour/foreground/depth-gap rejection tests remain passing.

The earlier voxel-centroid explanation was not established: v5_geometric_grasp._voxel keeps an original point, not a centroid. Fused geometry uses centroids, but this does not prove the historical collision came from voxel centroids. The above projection/mask evidence supersedes that conjecture.

Drawer diagnostic 7640_4/5 reached joint7=2.89776rad and missed the commanded pregrasp by21.6/24.8mm. be5d8f9 chooses the closer parallel-finger-symmetric orientation; it does not change joint limits, force, collision margins or endpoint tolerance. Physical repair effect is pending. c9f3d7a defers full-scene construction until opposition proposals exist; all actual candidate routes still undergo smooth sweep/IK/closure checking.78dc5ba adds measured thin-surface contact for bounded push nudges, never a claimed grasp.

Jobs7649/7650 use be5d8f9 on the same bowl, K1/K4, and have real physical requests. Job7647 tests the plate push contact from78dc5ba. The obsolete58effc3 development continuations were cancelled after preserving their partial choices and hashes (reports_20261016/obsolete_pre_be5d8f9.json on5880). The completed cup failure is preserved. No confirmation result, held job or protected c5/c6 job was changed. Category qualification still requires20 original episodes per category and remains incomplete.
