### Codex3 2026-10-08 PDT: microwave repair, motion replay and prediction accounting

Microwave source commit e0a6597549731414c47b4be737d083e9399d1ab2 adds the
default-off microwave_verified_view_fusion_v1 switch. Raw dual-view acquisition
is retained. Only views with current public clear-occlusion evidence contribute
endpoint planes; unknown views cannot make an independently clear view unknown.
Two clear but inconsistent views still fail the unchanged geometry checks.
No thresholds or private-label control were added. Focused microwave tests:
104 passed. Codex1/Codex2: this can change microwave endpoint receipts when
enabled; it is development-only, not a frozen renderer or training admission.

Job4790 is submitted once, pending resources at 2026-10-09 09:25 CST.
Same-source/launcher CPU preflight passed; actual physical startup remains
pending. Snapshot:
/public/home/sunyihan/rpent_libero_eval/source_v5_microwave_verified_view_20261009_r1
Source identity SHA256 bdbb9e88da800411a07c3abbe470312a9db0ee144d7c969ab95b4d7312cc783b.
Plan /public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave_verified_view_20261009_r1/stop_verified48.json
SHA256 e007306564e5e249accf2658d06a8e1100296adfd4fb2ea7f0d3d872beeb6d95.
No array release before this launcher produces its first actual physical request.
All eight GPUs are allocated; own4780 uses node02 four, Codex2 uses node01 four.
No other-owner job or node binding was changed.

Eight pinned original-task motion-prefix diagnostic cases contain201 actual
move_to calls,3 unreached. All3 have contact or near-joint-limit stagnation
evidence: Long t8/init2 above_10cm and yaw_90 residual13.99/13.88cm with moka
pot/link5 contact; Goal t2/init2 place residual25.18cm with self/bowl-link6
contact and joint2 near limit. This is evidence classification, not proof of
IK infeasibility or yaw causality. Four complete prefixes,1 native success,
3 physical-precondition divergences; exact request equality9/16 decisions.
Manifest /public/home/sunyihan/rpent_libero_eval/artifacts/motion_prefix_classified_20261009_r1/manifest.json
SHA256 82ddeb91c4a4a15d4ce630b7bc125232570977d78549ae7afb751e92d3ec1c32.
No training rows, confirmation states or qualification.

Codex2: the directly deliverable execution-before-prediction/same-run passive
simulation-label pairs are
/public/home/sunyihan/rpent_libero_eval/results/harness_v5/success578_delivery_20261008/complete_v1/paired_action_outcomes.jsonl
SHA256 38f5046c2ea44fbed624e6076638a627b18fb5a141298864ad2b7f1e092acd1f.
Source manifest SHA256 196b668f7a8057371f012444521d6b9b3dea01e82ade54bd1ec35d1eeb0aca78.
20 original diagnostic episodes,82 action predictions,57 usable truth labels
(34 positive/23 negative);25 truth_unknown retained,2 finish decisions separate.
Please use25 unknown:82-57 and the source manifest agree; the earlier21 count
does not match this complete_v1 cohort. No new model calls were made.
v5@750 revision b226f57a; AUROC0.896419, episode-bootstrap95CI
[0.762344,0.951728], Brier0.275761, ECE10 0.305836. At p>=0.9,14/48 failed.
Grasp36 AUROC0.930341; place11 all positive/AUROC undefined; vla_subtask10
AUROC1.0 is too small for a stable claim. top3 behavior remains disabled.
Fresh recomputation report
/public/home/sunyihan/rpent_libero_eval/results/harness_v5/success578_delivery_20261008/metrics_20261009_r1/report.json
SHA256 d8ef27a45b4d9831a61656daa102c1b7722880cb7fa76611aa1132af1ed87867.

All skill thresholds continue to be internal acceptance criteria. Confirmation
states/layouts remain permanently excluded from training. No behavior freeze
or final evaluation is claimed.
