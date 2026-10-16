# 10/16 bounded-skills physical development results

Source trajectory:84cf146. Updated executor fixes:d641e16, under single-case development. All runs are simulation only, training=false. No confirmation results are relabeled. Current oracle skill-chain qualification is incomplete.

## Paired waypoint sequences

20 original states x 3 fixed routes x 4 methods; n=60 per method. All attempted routes retained. Stops are measured troughs below5mm/s at intermediate waypoints; commanded stops remain separate.

|Method|Endpoint-complete routes|Jerk RMS median (m/s^3)|Path/chord median|Measured internal stops median|Max tracking residual median (m)|
|---|---:|---:|---:|---:|---:|
|legacy_move_to|60/60|9.3852|1.2981|0.0|0.03532|
|legacy_move|60/60|9.5318|1.2999|0.0|0.03573|
|smooth_k1|43/60|0.8807|1.2832|1.0|0.02476|
|smooth_k4|60/60|0.6467|1.3134|0.0|0.02042|

The old residual is distance to a per-command target; the new residual is distance to a timed trajectory reference. These residuals are not a same-definition comparison. K1 includes17 failed routes; its lower path ratio is not evidence that those routes completed. Old commands stop at each segment but no5mm/s trough was measured on these particular legacy routes.

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

Raw/derived evidence:reports/motion_c2.json,reports/motion_c3.json,reports/pi05_7528.json. Each contains hashed input ledgers and per-state records. Reports are exploratory development, not frozen confirmation.
