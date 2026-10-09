# Codex3 — closed RULE-N and full-task diagnostics

Recorded 2026-10-08 PDT / 2026-10-09 CST. All runs below are interim
development diagnostics, not skill confirmation or behavior-freeze evidence.
Primary metric: official physical success; correct_finish is secondary.
Skill qualification thresholds remain internal acceptance criteria.

## RULE-N 4743

Startup4740 plus array4743 cover the registered80 exactly once. Success26/80,
Wilson95 [0.232442,0.433595], budget49, over_token5, median wall560.0396s.
Maximum consecutive identical action5; episodes with >=20 repeats0.
Paired against current A3-N47/80: both-success26, A3-only21, RULE-only0,
both-failure33. Prior RULE28/80 and startup-failed4604 remain retained.

Manifest:
/public/home/sunyihan/rpent_libero_eval/results/harness_v5/interim574_20261007/RULE-N-retry_20261009/summary_20261009_interim/manifest.json
SHA256 e9427be56d3442c68220e2bb2075666438aaecd71b42f0da6db1b185f5bd5287.
Summary/once80/paired_flips are in the same directory.

## Full-task structure diagnostic

Expert startup4655 plus array4711:194/200, Wilson95 [0.936106,0.986180],
Spatial50/50, Object50/50, Goal48/50, Long46/50. Five no_legal_candidate,
one budget_exhausted; median wall34.4039s. Correct_finish0/200 because native
success terminates. The earlier199-array-row report omitted the retained
successful startup identity; it is now included once, without a rerun.

Against historical177/200:174 both-success,20 new-only,3 old-only,3 both-failure.
Against171/200:169 both-success,25 new-only,2 old-only,4 both-failure.
Against175/200:173 both-success,21 new-only,2 old-only,4 both-failure.
Source commit797fa84c3a246337ce669c8b4f8c1e409cbd183d; archive SHA256
f5dac5c52262e9d28af4e86a6e68cf0aa421e8781198d24ce62c29b58a9d444c.
Manifest /public/home/sunyihan/rpent_libero_eval/artifacts/fulltask_expert200_20261009_closed_r1/manifest.json
SHA256 d13ce7ee5668527d65980d0de2e86ebb202b96794204496ce9ed6122ffdb46d6.

A3-N startup4642 plus array4651:49/80, Wilson95 [0.502937,0.711754],
budget28, over_token3, median wall109.8793s. Versus ordinary A3-N47/80:
42 both-success,7 new-only,5 old-only,26 both-failure. The five regressions
have paired trace evidence; causal replay has not been performed.
Source commit34a02970b14e649843c222ea727866c0dc327327; archive SHA256
8fc9bccb2ae7b63dae96196e5dd995bcb5e53d8aa376be260ab98e85bddcb61e.
Manifest /public/home/sunyihan/rpent_libero_eval/artifacts/fulltask_A3N80_20261009_closed_r1/manifest.json
SHA256 f563763699eb030739ccf0b45a1fc85571dfa8cbf03bbc1aaedcdceffaaaaf7b.

Both manifests include immutable source, preparation, startup and result hashes.
Failure records and all previous reports are retained. No training admission.

## Active expert rerun

Job4780 retains source2ea629ee61338fdd83ef94e816b2726046b59167 and its
same-launcher startup4779. Increased own ArrayTaskThrottle2->4 after live
allocation showed node02 had2 free GPUs. Four shards now actually running;
node01's4 allocated GPUs belong to Codex2 and are untouched. No node binding.
200-episode rerun is incomplete; partial successes are not a final rate.
