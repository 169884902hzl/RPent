# 4178 complete measured-handle third-method smoke

SOURCE549 / 8b45399594355c79c2abe6c76a8badab010b8de4; complete30/30,6 shards COMPLETED0:0.25 original raw states,30 nominal resets. No confirmation/freeze claim.

| Fixture skill | Planned | Actual first motor motion | Actual first VLA contact | New endpoint | Missing current handle | Missing wrist handle | Missing binding |
|---|---:|---:|---:|---:|---:|---:|---:|
| drawer open |5|5|5|0|0|0|0|
| drawer close |5|5|2|0|0|3|0|
| microwave open |5|1|0|0|3|1|1|
| microwave close |5|0|0|0|5|0|0|
| stove on |5|5|5|5|0|0|0|
| stove off |5|3|0|0|2|3|0|

Five new endpoints out of12 real first VLA contacts; seven contacts did not achieve endpoint;18 cases never reached VLA contact. The report's19 physical attempts include7 motor-only approaches. Contact ready is not skill success. Public measured TP5/TN5, noFP/FN, null9 over19 known motor outcomes; measured agreement10/10 but full known-truth agreement10/19=52.63%.

Full30-case public audit:30/30 server/motion accounting matches,13600/13600 requested/executed VLA controls including4000 microwave-close setup, no native truncation/external truncation/private-truth control;53/53 explicit handle files have SHA and source-step matches. Stove on5/5 public verdicts recompute from public RGB-D inputs.

Largest ready-but-failed type is drawer_open5/5. All received fresh two-camera handle measurements and800 controls. Four keep the gripper at least7.8cm open; sampled TCP remains6.9–13.4cm from measured handle. Handle z≈0.953, approach target z≈1.207 and0.15m offset. The public original instruction was reordered from 'open the bottom drawer of the cabinet' to 'open the cabinet bottom drawer'. Same raw states under SOURCE544 current original prompt reached4/5 endpoints, but4 old successes used short native-done blocks. Start/approach, prompt order and execution exposure are confounded; no single cause is declared.

Next shared test: complete5 controls, same raw states and original public sentence, native start vs measured overhead approach; then isolate sentence order. One close attempt transiently latched native success but ended q=-0.000288 and final endpoint=false; preserve both facts. Runtime geometry is not replaced by private joint truth.

| Group | Setup VLA requested/executed | First VLA requested/executed | First non-VLA controls |
|---|---:|---:|---:|
| drawer_open/measured_fixture_handle160 | 0/0 | 4000/4000 | 478 |
| drawer_close/measured_fixture_handle160 | 0/0 | 1600/1600 | 331 |
| microwave_open/measured_fixture_handle160 | 4000/4000 | 0/0 | 49 |
| microwave_close/measured_fixture_handle160 | 0/0 | 0/0 | 0 |
| stove_turn_on/measured_fixture_handle160 | 0/0 | 4000/4000 | 567 |
| stove_turn_off/measured_fixture_handle160 | 0/0 | 0/0 | 121 |

Raw ledgers remain on both hosts with SHA verified; raw and gzip are not staged in Git. Precise references and per-case strata are in report.json/control_and_exclusive_audit.json.
