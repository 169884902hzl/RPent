#!/usr/bin/env bash
# Root submits this one visited development episode after checking the preceding smoke.
set -euo pipefail
sbatch --export=ALL,MICROWAVE_SOURCE=/public/home/sunyihan/rpent_libero_eval/source_v5_microwave583_20261007,MICROWAVE_PLAN=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave583_source_CPU_20261007/r1/close_stop40.json,MICROWAVE_PLAN_SHA=1a5c92bf90bdb32c85932646dde96319cee5ebd9a71fd8a417800d9d6ca49c4d,MICROWAVE_OUTPUT=/public/home/sunyihan/rpent_libero_eval/results/harness_v5/microwave583_temporal_original_20261007/close_stop40,MICROWAVE_CPU_ONLY=0 /public/home/sunyihan/rpent_libero_eval/source_v5_microwave583_20261007/coordination/microwave_runtime_wiring_20261007/run_smoke.sbatch
