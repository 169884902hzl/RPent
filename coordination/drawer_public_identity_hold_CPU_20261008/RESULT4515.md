# 4515 paired original-development evidence

This is one previously visited original LIBERO-90 t23/init20 state, paired with
4327. It is not a new qualification batch. No training rows or new GPU jobs were
created by this analysis. The old physical result and r1 CPU report are retained.

The runtime/source identity is unchanged from the registered v9 manifest:
`source_v5_drawer_endpoint_hold_v9_20261008`, commit
`40583453969c083e6146b38eced7f93b2d6e5646`. Source archive SHA256:
`0cee5fd5c9a57bf14243d16c8a08f8cdb76a2d578aadf1486f669a48436183ec`.
Manifest `results/harness_v5/drawer_endpoint_hold_v9_CPU_20261008/preparation/same_t23_s20.json`
SHA256 `bba74d6cdd94fbd40567cb93ca2fb23e53b690cdc1dbc7fd5f87ce052c7d1139`.
All remote paths below are relative to `/public/home/sunyihan/rpent_libero_eval`.

| Evidence | 4327 v6 | 4515 v9 |
| --- | --- | --- |
| Complete contact blocks | 10 | 160 |
| Contact controls executed | 50 | 800 |
| First private close after complete block | Never | 22 |
| Private close at final endpoint | false, q=-0.15768362 | true, q=0.00154406 |
| Public admitted close stop | 1, false positive | 0 |
| Public samples | 2 true | 160 null |
| Geometric endpoint candidates | 2 true | 75 true / 72 false / 13 null |
| Final public receipt | failed | unmeasured |
| Actual total controls | 137 | 938 |
| Original recorded executed_actions | 139 | 941 |
| Original counter's final-distance checks | 2 | 3 |
| Case wall seconds | 32.32 | 688.44 |

4515's release, contact clearance and view retreat all retain private close.
All private labels explicitly have `source=simulation_diagnostic_only` and
`used_for_control=false`. The full 160 contact blocks have requested and actual
length 5; no native-success truncation controlled contact. The private first
true block is a diagnostic, not an online stop rule. The public v9 close-face
identity is unqualified, so its stop and final verifier abstain. No neutral hold
was executed: this case does not physically validate v9's open endpoint hold.
Geometric candidates here are endpoint checks, not decision-model selections.

The saved `executed_actions` counter includes the terminal distance-check
iteration in each move. r2 uses saved `actions_used` where present, and actual
contact counts; the original rows were not edited. The old v6 samples have no
`stop_admitted` field, so r2 gets its one stop from the saved original receipt.
r1 incorrectly counted that legacy stop as zero and remains preserved.

- New ledger: `results/harness_v5/drawer_endpoint_hold_v9_CPU_20261008/physical_smoke/job4515/episodes.jsonl`; SHA256 `57c4c2ea6963e8ef42ba4b619e94fcef21bc939994f64b6bd27e567bb3b93fd5`.
- r2 report: `results/harness_v5/drawer_endpoint_hold_v9_CPU_20261008/paired4515_4327_r2/report.json`; SHA256 `2559d4f0727b1617da920dcc29dda62d14d867d58ce35cc0a064d00df5aa212d`.
- Paired records: same r2 directory `paired_records.jsonl`; SHA256 `060fa8218523523309f0338cfad0caa0de62f86d8f80e72ae6a2332e565a7a69`.
- CPU producer: `results/harness_v5/drawer_endpoint_hold_v9_CPU_20261008/summarize_job4515.py`; SHA256 `e6039e550f079a3a2455589bb39dfe3e311f99d2a3eac6ff0cb45f1c84b7481c`.

## Separate moving-placement fixes

These fixes do not alter the frozen source used by 4515 or its old records:

- `94b3a5b`: contact mode no longer returns a stale drawer after refresh failed
  to measure it. stale/occluded/missing cases are tested in both contact modes.
- `6b8de9b`: `execute_subtask` no longer replaces a fresh moving target with
  `target_cache.setdefault` before a placement segmentation query. A focused
  reproduction first failed because its query ROI used source_step=0 instead of
  the current drawer; it passes after the stationary-only cache guard.

Fresh CPU checks:
`python3 -m pytest tests/unit_tests/robots/libero/test_v5_moving_placement_target.py tests/unit_tests/robots/libero/test_v5_subtask_release_reverify.py tests/unit_tests/robots/libero/test_v5_subtask_observe_retreat.py -q`
returned 52 passed. The environment warns that pytest-timeout is not installed.
No new physical validation of these moving-target fixes has been performed.
