# Moka centre: fixed 11 closed original trials

CPU diagnosis of the report6 cohort. Existing labels and all raw trials remain unchanged. No new physics run, runtime change, training row, or qualification claim.

| Original seed | Sustained / target | Max clearance | Finger / dual samples | Public final visible / place | Diagnostic |
|---|---|---|---|---|---|
| 0 | True / True | 10.64 cm | 196 / 58 | False / None | target_satisfied |
| 1 | True / True | 11.30 cm | 240 / 131 | True / True | target_satisfied |
| 2 | False / False | 3.45 cm | 389 / 0 | False / None | brief_lift_without_0p5s_sustained_hold |
| 3 | False / False | 0.00 cm | 191 / 0 | True / False | finger_contact_without_3cm_lift |
| 4 | False / False | 0.00 cm | 63 / 0 | True / False | finger_contact_without_3cm_lift |
| 5 | False / False | 1.72 cm | 393 / 206 | False / None | finger_contact_without_3cm_lift |
| 6 | True / True | 16.10 cm | 208 / 0 | True / True | target_satisfied |
| 7 | False / False | 0.00 cm | 244 / 0 | False / None | finger_contact_without_3cm_lift |
| 8 | True / False | 12.72 cm | 167 / 0 | False / None | contact_lost_while_commanded_closed_target_not_satisfied |
| 9 | True / True | 8.00 cm | 274 / 35 | False / None | target_satisfied |
| 13 | True / True | 8.31 cm | 526 / 74 | False / None | target_satisfied |

All initial approach endpoints were within approximately 0.8–1.2 cm. The five no-sustained-hold failures are not endpoint-servo failures: seeds3/4/7 had no clearance; seed5 reached only1.72cm despite dual contact; seed2 had only a brief >=3cm contact lift.

Seed8 formed the existing sustained witness at18.70–19.20s. The first subsequent contact loss at19.35s still had a positive (closed) gripper command; the enclosing chunk ended with the opening narrowing from about50mm to6mm. Opening commands began only in the following chunk. Final table contact and false official target support a transport-slip diagnosis, rather than deliberate successful release.

Five final targets are true despite all stop reasons being chunk_budget. Seven public placement verdicts remain unknown; seven final object measurements are invisible cached measurements. Cached locations must not supply a missing final placement verdict.

The official labels, including seed5's false final target despite burner contact, are unchanged. Contact with a target surface alone does not replace the official predicate. Fixed11 is exploratory and cannot select or qualify a class skill card.

Legacy trace limitation: seed13's held-at-end flag coexists with burner contact and a single finger contact. The original truth helper excludes only the original table support; this flag is preserved and cannot be described as exclusive support by the gripper. Its earlier first sustained witness had no non-finger contact. Seed9's first witness contains one burner-contact sample, also retained as raw evidence.

Report SHA256: 47a85a0a28165d4033e8ca47f6bf6c0dce5a3a71d360c96beffedb2b7c398541
