# Conditional IK calibration correction

1. A conditional IK endpoint was being mistaken for a new calibration measurement. Prediction now retains the captured base transform while reseeding its joint solution; actual measured-route reseeding is unchanged.
2. The saved microwave-close context reproduces 0.487–0.844mm implicit base translation and 0.000383–0.000881rad rotation. Fixed-base conditional contact search finds a plan after all six 2cm nudges, versus five with the old predictor. This is CPU planning evidence, not physical success.
3. The related chunk/kinematics/offline suite passes41tests; two position/orientation residual cases pass separately. The regression first reproduced a4mm fictitious base translation. Existing pytest configuration and lint findings remain separate.
4. Public schema `bounded-skills/3` and legal contract `public-request-legal/2` are unchanged. Private judge advances to version9 because predicted-state labels can change. Codex1/Codex2 receive the source hashes and must keep source-specific labels separate.
5. Original-state oracle development and the lost-contact physical rerun continue under their immutable sources. The correction requires its own same-launcher physical startup before a complete replay; no freeze or training admission is claimed.

## Evidence and interpretation

`reports/microwave9248_6_predicted_base_CPU_20261018.json` pairs the two predictors on request9 of retained failure9248_6. Context SHA256 is `0f3015de3f0def2e1f936bdb0a54c265489dfda25ca8caba7d8312347c8b783f`. Each pair uses the same captured public pixels, calibration and robot state; no simulator, renderer, RPC, physics control or GPU is available. A predicted commanded pose and its tolerance-accepted joint solution are not an independent EEF/joint measurement. Calibrating again from them moves the fixed robot base by the IK residual. Keeping the captured transform removes that error without changing IK tolerances, collision geometry, robot limits or measured anchors.

This does not prove that a continuous route exists or that the microwave will close. The original eight noncolliding approach routes fail numerical IK near joint limits. Five measured panel patches and an extra2cm whole-route side leg did not yield a plan and cost more CPU; neither experiment is enabled. Reports and discarded patches remain in `reports/microwave9248_6_panel_{patches,side_route}_CPU_20261018.json` and `reports/panel_{patch,side_route}_candidate_not_enabled_20261018.patch`. Splitting a route also changes numerical continuation; the calibration correction does not explain every difference between a split and whole-route search.

The new real-chain regression checks both a4mm position residual and an additional0.02rad orientation residual. It asserts that prediction preserves calibration and original sensor state while adopting the commanded endpoint and predicted joint seed. The existing measured-route test continues to exercise actual sensor reseeding. Commands:

```bash
.venv/bin/python -m pytest -q tests/unit_tests/robots/libero/test_bounded_chunk.py tests/unit_tests/robots/libero/test_v5_grasp_kinematics.py tests/unit_tests/robots/libero/test_bounded_offline_labels.py
.venv/bin/python -m pytest -q tests/unit_tests/robots/libero/test_bounded_chunk.py -k conditional_ik_residual
```

The first command passed41tests in52.63s before the second angular case was added; the second passed both final regression cases in1.38s. Import-only style cleanup followed; no behavior changed. Source hashes and final scoped lint evidence accompany the delivery receipt. No repository-wide PR checks were run for this local development change.

## Latest complete source-specific cohort

At14:43PDT the ec89f74 round-robin cohort has16physical results,12successes and4retained failures; source-specific rows, category Wilson intervals, step counts and chunk distributions are in `reports/original20_support_roundrobin_20261018_progress.json`. Cup-init1 transferred one of two task objects, then exhausted measured options; drawer-open-init1 also failed. These failures are distinct from the two microwave failures and are not erased by a successful Slurm exit. Remaining cases are incomplete, not scored failures. Startup results are never counted as task success.

## Answers retained from the preceding delivery

The function-level profile, cache/parallelism conclusions, repaired common bowl-init2 failure, nonsemantic candidate order and latest-three detailed receipts are documented in [the10:05follow-up](progress_1005_offline_labels_20261018.md). The CPU prefix interface can fill Codex2's unknown positions only with their matching private captured measurement context. Eight actual contexts now match26online oracle positions; eight constructed alternative legal prefixes also label. They are not measured physical branches or actual model-selected prefixes. The historical26requests/59unknown positions lacking matching contexts remain unsupported.

All confirmation-state exclusions remain permanent. No models are trained. Existing physical failures and old labels are retained under their original source identities.
