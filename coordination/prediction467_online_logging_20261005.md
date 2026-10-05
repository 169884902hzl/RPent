# Codex3: online pre-action success diagnostics prepared while grasp array runs

Implemented default-off `--success-prediction-diagnostic` for the text-only
local System One path. It scores the selected action on the exact pre-action
context,after selection and before collection physical branches/execution.
Records candidate/index,context SHA,p_success,full request/response and both
HTTP/server compute timing in answer metadata. Selected action and original
action-choice probabilities remain unchanged;no new state/receipt lines.
Question uses the existing saved-state success-prediction spelling.

12 relevant success-choice/System One tests passed. Code commit2f15739:
`robots/libero/v5_success_choice.py::diagnose_selected_success`,
`harness_v5_eval.py` option and caller. No GPU request,model call or rollout
was performed for this new feature. AUROC/calibration therefore remain
unmeasured for online execution. Prior retrospective saved-prestate AUROC
does not become online evidence;action-choice probabilities are not physical
success probabilities. Future analysis must use matching executed-candidate
outcomes and leave unverified/unknown outcomes unscored.

This independent preparation does not enable top3 selection,change the grasp
cohort or alter active sources.3550 continues fixed115ba66;3554 waits for all
18shards;3565 waits for the same array using immutablea95e29e. No new Slurm
submission/no behavior freeze. Maintain unchanged95/90/95 grasp gates and
only run A3/A4 after those gates;freeze and training admission remain unfinished.
