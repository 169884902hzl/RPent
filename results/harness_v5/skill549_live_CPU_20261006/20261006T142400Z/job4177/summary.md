# 4177 complete development placement smoke

SOURCE548 / cf73d85; complete40/40,8 shards COMPLETED0:0. All20 original raw states remain; no outcome was replayed or relabeled.

| Relation / method | Planned | Actual first physical | New endpoint | Preserved before=true | No first |
|---|---:|---:|---:|---:|---:|
| in/current160 |10|6|4|2|4|
| in/vla_subtask160 |10|9|6|2|1|
| on/current160 |10|8|5|0|2|
| on/vla_subtask160 |10|6|4|0|4|

Overall endpoints23/29=19 new+4 preserved. Public TP15, FN5, TN6, FP0, null3; measured precision15/15 with Wilson[79.61%,100%], measured recall15/20=75% with Wilson[53.13%,88.81%]. Agreement over known truth21/29=72.41%; null is retained.

Legacy sustained setup truth32/40 and first placement19/24 remain in report.json. All-current-support v2 labels already saved in the same records give setup30/40 and true-setup first placement18/23=78.26%. Two legacy true/v2 false setup records touch white_cabinet_1_g29; one had no first execution, the other was t24/s2 vla. These are separately disclosed strata, not retroactive edits.

SOURCE548 has incomplete five-control chunks. Setup and first exposure is below; current on uses measured motor placement rather than VLA chunks. Absence of legacy contact_vla fields means unknown, never zero. This smoke is not a fair complete-budget method comparison or confirmation. SOURCE553 same40 CPU preparation fixes execution exposure prospectively.

| Group | Setup VLA requested/executed | First VLA requested/executed | First non-VLA controls |
|---|---:|---:|---:|
| place_in/current160 | 5095/2603 | 855/436 | 212 |
| place_on/current160 | 2545/2545 | 0/0 | 1155 |
| place_in/vla_subtask160 | 3805/2566 | 7200/2263 | 0 |
| place_on/vla_subtask160 | 3540/3540 | 4800/2366 | 0 |

Raw ledgers remain on both hosts with SHA verified; raw and gzip are not staged in Git. Precise references and per-case strata are in report.json/control_and_exclusive_audit.json.
