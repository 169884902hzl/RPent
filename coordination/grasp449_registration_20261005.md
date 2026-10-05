# Codex3: shared grasp bottleneck and original-task paired comparison

Accepted the 2026-10-05 01:45 PDT instruction, preserving the 01:30 report
repair and all previous runs. Grasp is the highest-priority shared bottleneck.
No behavior freeze or v5.1 training admission is asserted.

GPU reservation: two one-GPU workers, without ReqNodeList or ExcNodeList.
The startup probe waits for 3428 to return its two development GPUs; the full
cohort depends on a clean startup probe. This dependency enforces the existing
two-GPU development limit; it is not a scientific dependency. All runs are
original-task diagnostics, not PRO results or training rows.

Source: `/public/home/sunyihan/rpent_libero_eval/source_v5_grasp449_20261005`.
Interpreter: `/public/home/sunyihan/rpent_libero_eval/.venv/bin/python`.
Entrypoint: `scripts/probe_v5_grasp449_20261005.py`.
Output root: `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/grasp449_original_paired_20261005/`.
Job IDs will be appended immediately after Slurm assigns them.

Registered full cohort: 2,400 first attempts, six groups times eight conditions
times 50 identical paired original task/init states. Conditions: current
direct/above_10cm/yaw_90/restage; measured overhead plus short prompt; reset
pose plus complete original instruction; the latter two with 160 chunks
instead of 80. Common environment budget is 10,000 actions. Actual five-action
chunks, contact samples and wall time are recorded. Startup probe has 48 cases.

Categories: bowl, mug, bottle, box, moka pot, frypan. The original 40-task goal
set uses frypan as a scene object, not a source goal. Its complete probe prompt
is registered as "pick up the frypan and lift it clear of its starting surface";
other complete prompts are the original task language. This exception is
reported instead of pretending the original moka-pot instruction requests a
frypan grasp. Only original BDDL sources are read for this diagnostic.

Private dual-finger contacts and body displacement are written separately.
They never choose actions or enter state/request/receipt text. Report contact
and contact-plus-3cm-lift confusion separately, including ambiguous bindings.
No unexecuted grasp is a success or a negative physical label.

Full manifest SHA256:
`82bf8bf9057f4e8bbc46bb7deb8aa56027225fc53864ba14a5b66ca273c4693f`.
Smoke manifest SHA256:
`250bcf47b795175be2c2146d424a3d189be8c217c589851588dae6225e3d3b98`.

Two supported repairs are separately pending physical validation:

- Cooldown now removes only the matching `execution_error` action for three
  decisions. Recoverable measured motion failures stay eligible. No state
  line/field was added; existing failure counts remain visible.
- Strict placement/6 abstains for anchor-derived table areas lacking a
  measured support surface. Offline recomputation on 3414 gives TP60/FP1,
  precision 0.983607, recall including abstentions 0.419580. This is saved
  evidence recomputation, not a new physical validation or freeze. Report SHA:
  `292f1e12e4dd1b09cbbbc3c9297512ab6f0daef0a25351263fc90ce922d0cc66`.

Codex1/Codex2: receipt semantics change for strict placement/6. Wait for the
validated freeze identity before rerender/admission. Online and offline share
the same verifier and unknown reason. All 54 focused CPU tests passed; an old
test expectation that also cooled down measured failures was updated to the
user's explicit execution-error-only rule.

3428 remains diagnostic prefixes. Nine A4 regressions are retained; cards were
absent in both compared runs. A4/A3 old/new closed loops remain required after
the grasp combination is physically selected. No claim that the regression is
fixed is made from prefix replay or CPU tests.
