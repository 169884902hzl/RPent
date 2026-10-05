# Original-task placement false-positive diagnosis

CPU-only development analysis. No runtime edits, physical reruns, old-label changes or qualification claim.

Explicit source: original job3414 placement_report.json (174 recomputable attempts; 13 unavailable attempts stay in the old report). All 140 distinct original choices files matched their recorded SHA256 and reproduced the saved v5 verdicts.

| Rule on the same saved 174 events | TP | FP | TN | FN | Positive / negative abstentions | Precision | Recall including abstentions |
|---|---:|---:|---:|---:|---:|---:|---:|
| v5 recorded rule | 61 | 4 | 19 | 33 | 49 / 8 | 93.85% | 42.66% |
| current strict6 | 60 | 1 | 15 | 30 | 53 / 15 | 98.36% | 41.96% |
| exploratory current visible target bbox | 37 | 1 | 15 | 53 | 53 / 15 | 97.37% | 25.87% |
| exploratory 2 cm cache-change abstention | 11 | 0 | 15 | 30 | 102 / 16 | 100% | 7.69% |

The last two checks are analyses only and have not been installed. The same data informed their diagnosis; these figures cannot establish independent precision.

## Four old v5 false positives

- Original libero_10 task6 init0 decision3, init1 decision3, init2 decision6: target is `area right of plate`, extent `measured_anchor_region`. This supplies a destination from an anchor, not a measured support surface. Its zero-height region is nevertheless passed to the old support-height test. Strict6 abstains on all three; it does not make them successes or negatives.
- Original libero_spatial task4 init4 decision3: bowl on plate. Cache is plate source_step0. New public plate measurement source_step8 has centre difference 5.62 cm. The old cached rectangle fully covers the measured bowl footprint; the newer visible rectangle does not. The saved source steps8/9 are distinct and measured 3.19 seconds apart, so this is not the missing-two-frame case. Lower bowl surface is only 1.46 mm below the cached plate top, which passes the 1 cm band. Public images show the bowl tilted at the plate edge. The cached-support assumption and incomplete visible geometry admit this state despite the official predicate being false. Saved data alone cannot separate physical plate movement from occlusion-induced visible-bound changes.

## Candidate repair direction

1. Retain strict6's explicit unknown for anchor-derived regions until a public support surface is measured. A coordinate relation supplies a goal region, not contact evidence.
2. For physical supports, compare the cached complete pre-action support against fresh multi-view support evidence and qualify its visible coverage/rigid pose. Detect meaningful disagreement, remeasure from an unobstructed view, and keep ambiguous support unknown. Fit the plate/support geometry rather than replace its entire cached footprint with a partially occluded visible AABB.
3. Audit the bottom/contact estimate separately from two-frame centre stability. A stable tilted/overhanging visible surface can satisfy the present AABB and lower-height band; stability alone cannot prove correct support.

A naive current-target replacement loses 23 old true positives and introduces a new stove false positive (original Goal task1 init0 decision2). A 2 cm centre-change guard abstains on 49 old true positives. Neither should be adopted as a threshold fix. Positive old strict6 placements already have median public target-centre change 2.90 cm, so visible-bounds drift is common.

## Fixed new smoke prefix

3637 part3 was read once as a four-row closed prefix. Two original tasks (Goal task8 and Object task1, init0) each have current160 and endpoint160 arms; source runtime rules are strict5 twice and strict6 twice. Physical labels are three true and one false. Both v5 and v6 recomputation give TP2/TN1/positive-abstention1, precision2/2 and recall2/3. This is only a development smoke, not a completed placement confirmation. The prefix is persisted in the remote report directory with its hash in report.json; source ledgers and labels are unchanged.

The Object task1 `cream cheese in basket` endpoint160 subtask has two visible, distinct frames and verifies the physically successful `in` result. Its current160 `place` counterpart is physically successful but both saved frames are invisible copies at source_step5 (`two_frame_evidence_missing`), so it abstains; it is not a physical failure. The bowl/plate current160 is correctly negative and endpoint160 correctly positive. Endpoint160 executes `vla_subtask` while current160 executes `place`; they also differ in runtime rule, so this is not a single-factor verifier comparison. Recomputing both rules on each same saved measurement gives identical verdicts. Four episodes do not establish independent precision.

## Reproduction

```bash
cd /public/home/sunyihan/rpent_libero_eval/source_v5_skill511_json_repaired_20261005
PYTHONPATH=. /public/home/sunyihan/rpent_libero_eval/.venv/bin/python \
  /public/home/sunyihan/rpent_libero_eval/scripts/diagnose_v5_place_fp_public.py \
  --manifest /public/home/sunyihan/rpent_libero_eval/results/harness_v5/place_fp512_original_CPU_20261005/preparation/inputs.json \
  --output /public/home/sunyihan/rpent_libero_eval/results/harness_v5/place_fp512_original_CPU_20261005/report_capture2
```

The original report and all original choices SHA are checked. The output directory must be new; the source smoke ledger is live, so its preserved closed prefix defines the four-row evidence above. Full hashes and exact trace/frame steps are in report.json.
