# Closed precontact pair and follow-up

1. Final source ec89f74 pair9243 is complete: new4/4 and legacy4/4 native successes. Every new arm uses2decisions versus5legacy; these are four targeted development states, not category qualification.
2. At all four equal-control prefixes, simulator-state and control-sequence hashes match exactly. Public requests differ only in observation_id, revision and receipt history; anchors, robot measurements and candidate consequences match.
3. Separate c1bc859 pair9239_17 also succeeds in both arms. Fresh same-launcher startup9247_23 gates the new220-state ec89f74 oracle cohort9248; old-source completed/running records retain their source and denominator.
4. Two further cup CPU checks isolate the remaining boundary issue: init8's lift route clears with 54 correct target additions; init9 remains rejected after 3076 correct additions, with four true target samples still classified as obstacles. These are zero-control checks, not physical repair claims.
5. Codex3 continues the physical array and public-depth diagnosis. Codex2 can use the delivered captured-context prefix interface; missing historical contexts remain unsupported. No training, confirmation admission, or freeze is claimed.

## Same-source, same-state comparison

| Original bowl init17 | New chunk | Legacy chunk |
| --- | ---: | ---: |
| Native task success | true | true |
| Decisions | 2 | 5 |
| Simulation steps | 300 | 300 |
| Wall seconds | 320.771 | 483.630 |
| Actions actually executed per decision | 3, 4 | 2, 1, 1, 2, 1 |

This is a targeted original-state development pair, not a category rate. Source is c1bc859, not ec89f74. First-chunk controls match exactly at tick203, as do the simulator flat state and actuator model/data/robot components. Saved RNG state differs; the entire private snapshot is not byte-identical. The corresponding legacy request is index2. There are no anchor or candidate-consequence differences. Evidence: `reports/chunk_v3_precontact_stationary_20261018_paired_latest.json`, `reports/9239_17_equal_tick_CPU_20261018.json`.

The measured client-wall ledger uses exclusive main-thread buckets, unlike the overlapping cumulative function profile:

| Wall-time bucket | New chunk seconds | Legacy seconds |
| --- | ---: | ---: |
| Segmentation | 48.688 | 47.536 |
| Entity measurement | 78.774 | 99.670 |
| Depth and capture/transport | 10.621 | 10.868 |
| Consequences and request planning | 149.840 | 267.799 |
| Oracle decision, excluding nested planning | 3.645 | 6.750 |
| Simulation step/render | 7.616 | 8.013 |
| Private offline-label capture | 12.195 | 30.311 |
| Artifact IO, execution overhead, unattributed | 9.393 | 12.684 |

Both arms make101segmentation calls and8scene refreshes. On this pair, the new rule saves repeated request/measurement work while retaining per-action observations. Planning plus perception still account for about90% of the new wall time. This one pair does not establish a general throughput improvement. The profile/cache/parallelism analysis in the earlier report remains applicable: candidate processes share IK warm starts and cannot be forked independently while promising identical candidate consequences.

Both arms' nominal spline joins have maximum translation-acceleration jump2.744e-13m/s² and maximum jerk/limit ratio0.997006. These nominal-reference metrics do not certify all executed braking or cross-skill joins.

## Final-source startup and formal comparison

Startup9242_22 is `COMPLETED 0:0`, with one decision and202simulation controls in76.349wall seconds. It intentionally stops after the startup proof and is not a task-success trial. The existing launcher verifies its first physical request before submitting9243. Snapshot and archive hashes remain those in `progress_precontact_support_20261018.md`. Full submission evidence is `reports/chunk_v3_support_plane_20261018_full_submission.json`.

| Original state | Native success new / legacy | Decisions new / legacy | Simulation steps new / legacy | Wall seconds new / legacy |
| --- | --- | --- | --- | --- |
| Bowl init17 | true / true | 2 / 5 | 300 / 300 | 283.727 / 427.942 |
| Can init2 | true / true | 2 / 5 | 445 / 445 | 208.809 / 257.276 |
| Can init5 | true / true | 2 / 5 | 493 / 492 | 212.411 / 269.426 |
| Can init19 | true / true | 2 / 5 | 431 / 432 | 228.004 / 281.140 |

New actual-action counts are3,4in every episode. Legacy counts are2,1,1,2,1. No nonterminal suffix interruption occurs in these eight arms. The first prefixes have203/202/246/188controls, respectively. All four corresponding private simulator states and control arrays are exactly equal; public request differences are limited to IDs/revision/history. Evidence: `reports/chunk_v3_support_plane_20261018_paired_latest.json`, `reports/9243_all_equal_tick_CPU_20261018.json`. A one-step difference at native termination is retained in the final-step counts, not rounded away.

The same220registered cases now have a round-robin manifest across11categories,20states each, with unchanged case contents, seeds, goals, limits and budgets. Its CPU preflight passes. Fresh startup9247_23 uses this manifest, snapshot and launcher and completes0:0before submission of formal array9248. Oracle calls to pi0.5 remain disabled. The old ff00387 pending shards are cancelled using Slurm's PENDING state filter; completed and running records remain intact. Old running80/81/82 continue naturally. Neither cohort is silently combined or relabelled. A single resource/accounting controller follows9248, still honoring node02/nice500 and the returning Codex2 lane. Evidence: `reports/original20_support_roundrobin_preparation_CPU_20261018.json`, `reports/original20_support_roundrobin_20261018_full_submission.json`, and `reports/original20_old_source_pending_superseded_20261018.json`.

## Further cup diagnostics

The first cup init8 replay failed because its source anchor only becomes visible after an initial scan. The replay helper had assumed row0 always supplied the reference. It now selects the earliest preceding capture containing that anchor's public contact geometry and perception evidence; the same physical state is preserved. One attempt also used a nonexistent source path; the correct immutable path was recovered from the submission receipt before rerunning. These CPU-tool failures are not physical task outcomes.

| Original cup state | Baseline CPU lift | Corrected CPU lift | Added / removed | Independent added-pixel identity |
| --- | --- | --- | ---: | --- |
| init8 / 9026_68 | rejected | passed | 54 / 4 | 54 mug, 0 other |
| init9 / 9026_69 | rejected | rejected | 3076 / 3 | 3076 mug, 0 other |

All four remaining init9 blockers are also mug pixels. Restored simulation-state error is zero in both identity audits; no controls or GPU are used. The final candidate code has not yet been physically tested on these cup states. Evidence: `reports/9026_{68,69}_support_final_CPU_20261018.json`, `reports/cup{68,69}_support_identity_CPU_20261018.json`.

For can init6, the blocker is an isolated self-filtered depth sample at the occluded silhouette: its neighbouring image pixels are filtered or lie on a surface about149mm away. There is no current 3mm depth connection to the target. The current evidence does not justify labelling all pixels within the object box as its surface. The public neighbour diagnostic is retained in `reports/9026_26_precontact_islands_CPU_20261018.json`. Can init8 is separately retained; no identity or clearance threshold has been relaxed to clear either route.

## Requested interfaces and timing

The five 10:05 questions, function-level top15 profile and calls, cache/parallelism assessment, actual-capture prefix-label comparisons, nonsemantic candidate order and three-receipt history limit remain in `progress_1005_offline_labels_20261018.md`. They are not inferred from the cup geometry checks. Public schema/contract bytes remain unchanged.
