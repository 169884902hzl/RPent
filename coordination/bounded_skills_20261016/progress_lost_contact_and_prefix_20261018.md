# Lost-contact recovery and additional CPU prefix evidence

1. The microwave-open failure at9248_7 omits an existing legal recovery: the contact fit is gone, the active source is unchanged, no payload is held, and the hand remains closed. Private oracle rules8 reopen the hand before trying another scan.
2. This is a CPU-supported correction, not a physical success claim. The preserved request reproduces `NoPublicOption` with rules7 and selects its legal open-gripper candidate with rules8.
3. Focused CPU validation passes250tests; public schema and `legal_after` bytes are unchanged. A new immutable source and same-launcher physical startup precede the full microwave rerun.
4. Additional captured-state CPU checks match online labels at13positions in four contexts. Together with the previously delivered three contexts,24positions in seven contexts match; seven constructed alternative prefixes also return labels.
5. Captured contexts can fill Codex2's unknown positions. Historical records lacking the matching measured context remain unsupported; the alternative prefixes are constructed, not actual model outputs. No training or confirmation admission.

## Reproduction and limits

The original microwave-open record is `job9248_7/microwave_open_libero_90_t35_s0_oracle_k4`, state13. Its captured context SHA256 is `326638d4419995e98acd72529c9bb250f745311ab3399544381515a9dddf35ef`. The measured gripper opening is0.0250556m; `active=e98`, `held=null`, and the contact plan is absent. Both versions see the same request and the same public legal list. Rules8 choose `set_gripper(open)`; rules7 raise `NoPublicOption`. The recovery is limited to the active source with no held payload and a closed hand. It does not add a public candidate or bypass collision screening.

Evidence: [CPU replay](reports/microwave9248_7_lost_contact_oracle_CPU_20261018.json), [validation and source hashes](reports/lost_contact_recovery_validation_CPU_20261018.json). Test command: `.venv/bin/python -m pytest -q tests/unit_tests/robots/libero/test_bounded_skills.py tests/unit_tests/robots/libero/test_bounded_chunk.py tests/unit_tests/robots/libero/test_bounded_offline_labels.py` —250passed in162.96s. Existing pytest timeout warning and existing lint findings are retained; no new lint findings. Launcher/monitor compile and diff whitespace checks pass.

## Additional actual-capture labels

These contexts and online references use source ec89f74/private rules7. They do not validate rules8 or physical counterfactual outcomes.

| Context | Oracle positions | Mismatches | Maximum CPU seconds | Compressed context bytes |
| --- | ---: | ---: | ---: | ---: |
|9248_0 bowl, row0|3|0|27.988|122946231|
|9248_1 soup can, row0|3|0|17.491|82737259|
|9248_2 container, row0|3|0|9.922|84433867|
|9248_5 drawer open, row0|4|0|63.737|141177881|

Each context also labels one alternative legal nudge prefix using only CPU. Reports are `reports/offline_prefix_9248_{0,1,2,5}_CPU_20261018.json`. Prior contexts are9046_120(row0),9209_120(row3), and9248_3(row0). The private interface remains `libero-offline-prefix-label/1`: `annotate_prefix(state, request, prefix)`. The label's judge version now comes from the same oracle constant used online.

## Continuing physical development

At14:18PDT, source ec89f74's round-robin220-state oracle cohort has13physical results:11successes and2retained microwave failures(open and close), with no execution errors. This is incomplete development evidence, not a pooled qualification result. The two microwave failures require separate physical recovery checks. Their original records remain intact. The already matched440historical control episodes are reusable as documented in `progress_existing_controls_and_prefix_20261018.md`; they are not missing runs. The additional actual-box20states are separately registered and startup-gated.

The function-level profile, common bowl-init2 repair, candidate-order semantics and last-three detailed receipts are answered in `progress_1005_offline_labels_20261018.md`. The remaining work is physical microwave recovery, complete category upper bounds, then the requested K1/K4 and smoothness comparisons and forked branches. All original confirmation exclusions remain permanent.
