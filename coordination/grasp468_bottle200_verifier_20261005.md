# Codex3: completed bottle200 saved-frame verifier cross-check

CPU diagnostic consumed exactly3550_0/_1's200 closed first trials,verifying
all saved choices hashes. No physics/GPU/model calls or training rows.
Actual command:

```bash
/public/home/sunyihan/rpent_libero_eval/.venv/bin/python /public/home/sunyihan/rpent_libero_eval/runtime_launchers/diagnose_v5_grasp461_measurements.py --ledger /public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp459_bound_safe_retry1_20261005/full_job3550/part0/episodes.jsonl --ledger /public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp459_bound_safe_retry1_20261005/full_job3550/part1/episodes.jsonl --output /public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp468_bottle200_verifier_CPU_20261005/report.json
```

Report SHA256 `09e0b0bce10aa10c265e80857f46807a953ac6035292048f6f67c2bf75f6a205`.
Recorded and all three post-frame hypotheses(centre2mm,centre5mm,lower2mm)
give TP188/TN5/FP2/FN5,agreement193/200=96.5%.On this bottle-only corpus,
changing centre to lower bound adds no new false negatives but cannot fix
two later drops. False-positive direction2/7 actual negatives=28.5714%;
false-negative direction5/193 actual positives=2.59067%.
Three false negatives lack a fresh visual measurement,two have measured
centre rise below3cm despite sufficient true whole-body clearance. Physical
failures:2 loss of sustained support,5 no final lift/hold.

These are two already completed conditions on the same class,not an overall
six-class qualification or a new physical verification of the stricter
two-frame helper.3550continues;3554/3565keepdependencies.No freeze/admission.
