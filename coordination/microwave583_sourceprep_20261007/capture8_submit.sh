#!/usr/bin/env bash
# Root submits this one visited development episode after checking the preceding smoke.
set -euo pipefail
sbatch --export=ALL,MICROWAVE_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_microwave583_20261007,MICROWAVE_PLAN=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave583_source_CPU_20261007/r1/capture8.json,MICROWAVE_PLAN_SHA=1df559ce429bf005d71d174173390f5c2cee0e0610517b29803e4efdaba2d4cd,MICROWAVE_OUTPUT=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave583_temporal_original_20261007/capture8,MICROWAVE_CPU_ONLY=0 /public/home/sunyihan/rpent_libero_eval/source_v5_microwave583_20261007/coordination/microwave_runtime_wiring_20261007/run_smoke.sbatch
