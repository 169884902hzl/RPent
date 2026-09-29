# v5 engineering checkpoint, 2026-09-29

These are original-task engineering episodes, not the 40x5 oracle gate or training data. The simulator and execution budgets are unchanged within each reproduction pair. Previous results remain immutable.

| Job | Source | Task | Native physical completion | Explicit correct finish | Note |
| --- | --- | --- | --- | --- | --- |
| 2563 | 1d1cf00 | Spatial/0/0 | false | false | Script grasped small bowl instead of the instructed between-bowl; wrong finish preserved. |
| 2639 | 6377518 | Spatial/0/0 | Stored false; stale toolkit cache | Stored false | Oracle selected the correct measured instance; native completion did not update the toolkit cache. No retrospective score replacement. |
| 2641 | 3794fb7 | Spatial/0/0 | true | true | Composite captures publish native termination via get_env_state. |

2641 executed `grasp(e99,direct)`, then `finish()`. Native terminated=true/truncated=false. Its visual grasp receipt stayed false: the contact chunks completed the official placement goal without a measured 3cm lift. Physical completion and grasp verification are separate. Wall72.77s, initialization66.72s, contact-step total5.48s (perception0.58s, execution4.83s, script choice0.002s); the <=5s target is not achieved. Full prompts1677/1734 tokens,24 candidates, no simulator identifiers or predicates in actual requests. The request audit passed2/2. Qualified formal training rows:0.

Commands/interpreter:

```sh
sbatch --parsable --export=ALL,SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_3794fb7 /public/home/sunyihan/rpent_libero_eval/source_v5_3794fb7/run_v5_oracle_smoke.sbatch
# /public/home/sunyihan/rpent_libero_eval/.venv/bin/python
sbatch --parsable --export=ALL,SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_5153dc0 /public/home/sunyihan/rpent_libero_eval/source_v5_5153dc0/run_v5_oracle_development.sbatch
```

2645 runs four original engineering episodes (Spatial/Object/Goal/10 task0/seed0),24 decisions/40 contact chunks/3000 environment steps, with warm SAM/Pi0.5 services. It checks the pause marker between episodes. Its manifest and submitted source are immutable; its result is not claimed here. The 40x5 gate, Jev v5 gate, Table A, formal dataset and v5 freeze remain pending.

Private snapshot engineering probe2630 passed physics/proprioception/predicate restoration. Production-threshold fixed-frame SAM probe2631 detects three generic bowls but no reliable black-bowl/ramekin fine categories. Oracle binding uses measured extents and instruction relations; unresolved references select help. No simulator pose is used for executor targets.

Public GPT-5.5 memory revision and all443 file hashes are in `public_memory_pin.json` and `public_memory_receipt.json`; remote hashes443/443 passed. The asset is inference-only, not an oracle or training source. Dataset license is NOT_PROVIDED. No memory-assisted evaluation is claimed.
