# skill516: safe centre / measured handle full-subtask exploration

Accepted parent request: independent prepare script and launcher only. No change to probe501, runtime, old confirmation source or training40 boundary. Parent owns final source, COORDINATION/push and Slurm. No Slurm submitted by child.

The CPU prepare command completed successfully on gpu5880-ts. It reads only the explicitly named skill500 `preparation_v2/full.json` and gripper513 `runtime_calibration.json`, checking both SHA-256 before use. No artifact discovery, PRO configuration or sealed/user test text is read.

400 requests: pan/moka × safe measured-bounds centre / currently measured true handle × 100 nominal requests. Every arm preserves the parent's original `libero_10/task2` initial states 0–49 repeated twice, giving 50 unique scene states per arm (50 across the entire batch). Repetitions, full state-SHA sequences and seed sequence hashes are recorded in registration. This batch is explicitly `qualification=false`, `confirmation=false`, `new_training_rows=0`; it cannot establish the independent-confirmation threshold.

Both arms run a full single transfer subtask using the original-style public phrases `put the frying pan on the stove` / `put the moka pot on the stove`, with 160 chunks, 5 actions per chunk, and a measured safe approach 0.10 m above the object. Original40/90 are permitted for single-skill exploration only; this batch uses only the explicit original40 parent cases. It adds no tasks to training.

Exact condition keys:

- centre: `contact_approach="measured_bounds_centre"`
- handle: `contact_approach="measured_handle"`, `contact_approach_fallback="measured_bounds_centre"`
- shared overrides: `grasp_independent_views_v1=true`, `grasp_measurement_calibration=<complete explicit calibration JSON>`

Handle fallback must be marked as measured-bounds centre when no true handle is currently measured, never represented as a synthetic handle. Parent coordinates the probe501 implementation; prepare516 does not implement motion or substitute private geometry. Sustained grasp, measured public receipt and completed transfer remain separate metrics; a deliberate release after transfer is not sustained-grasp success.

Artifacts under `/public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill516_safe_subtask_exploration_20261005/preparation/`:

| File | SHA-256 |
| --- | --- |
| full.json (400 requests) | a493a63045abc7b79ea6e351ed40d75c2b70736679edbf94cf05508056a13175 |
| smoke.json (four requests, one per type/arm) | 57a8860dd0777803eedfffcbfd1e7ec427761a3af19a7e8338c1f94c6415d70e |
| registration.json | 0d3cb353f0fb060b5e3fc2393135b9aca36099eab7a5cef42246a2e0d7d991be |
| parent skill500 preparation_v2/full.json | 4cf765257b86229ee624499adfca72b2359bb4069331fbd9227c598061ce0b92 |
| complete gripper513 runtime_calibration.json | d4d977a5e5c23a23d80983ab34a4958373c6103035c2156ced24038204e4ca1c |

All registered case/seed records SHA: `d1e631c45592e67b7717e43f9f921930ccce85f3e8e3afd3563a855270fc27e7`. Each arm's ordered episode/seed sequence SHA: `e82c3261bf9c77ca313bf94ac26ff366e4b37924bd7f6cfdc48e3255ebbcc4d5`.

Actual completed prepare command:

```bash
python3 /public/home/sunyihan/rpent_libero_eval/scripts/prepare_v5_skill516_safe_subtasks.py \
  --parent-manifest /public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill500_original_comparisons_20261005/preparation_v2/full.json \
  --parent-sha256 4cf765257b86229ee624499adfca72b2359bb4069331fbd9227c598061ce0b92 \
  --calibration /public/home/sunyihan/rpent_libero_eval/results/harness_v5/gripper513_original_opening_calibration_20261005/runtime_calibration.json \
  --calibration-sha256 d4d977a5e5c23a23d80983ab34a4958373c6103035c2156ced24038204e4ca1c \
  --output /public/home/sunyihan/rpent_libero_eval/results/harness_v5/skill516_safe_subtask_exploration_20261005/preparation
```

Launcher `scripts/run_v5_skill516_safe_subtasks.sbatch`: one GPU / eight CPUs per part, eight parts, throttle eight, no ReqNodeList/ExcNodeList/dependency. Mandatory parent-supplied `SKILL516_SOURCE` and `SKILL516_MANIFEST_SHA` ensure it uses the final isolated source and registered manifest. Full output will be `.../skill516_safe_subtask_exploration_20261005/exploration_job<array-job>/part<array-index>/`.

For parent smoke submission after integration: array 0–3 with `SKILL516_SHARDS=4`, `SKILL516_MANIFEST=<preparation/smoke.json>` and its registered SHA. For full run: default eight parts and full manifest SHA. No job numbers fabricated or source snapshot created.

Source SHA-256: prepare script `62c27170b50a2b57f5f9d84dbbbfe5973574aa6e7c5de9f809cc4bfc5bc6689b`; launcher `e9fd840a19dbaa06e3f321a5c68d4ac8c6bf7f2c3f9ebdcfc7b669f8ccb049a3`.

Checked: CPU prepare exit 0, counts 100 per type/arm and 400 unique request names, explicit SHA audit, launcher `bash -n` exit 0. Runtime integration, GPU smoke and physical outcomes await parent; no claim they already passed.
