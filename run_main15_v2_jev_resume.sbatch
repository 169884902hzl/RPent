#!/bin/bash
#SBATCH --job-name=libero-v2-jev-resume
#SBATCH --partition=gpu
#SBATCH --nodelist=node02
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=12:00:00
#SBATCH --nice=10000
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail

ROOT=/public/home/sunyihan/rpent_libero_eval
cd "$ROOT"
RESULTS_ROOT=results/main15_v2_completion_20260929
mkdir -p "$RESULTS_ROOT"
printf '%s  %s\n' \
    956b37f677da971449db861e64dfc6589fd67ca8c8949b4a9dea3f9275bfcc77 \
    typed_choice_eval.py | sha256sum --check
curl -fsS --max-time 5 http://127.0.0.1:18574/health

for task in 2 3 4 5 6 7 8 9; do
    if [ -f "$RESULTS_ROOT/PAUSE_REQUESTED" ]; then
        echo "GPU yield requested; releasing after completed episode."
        exit 0
    fi
    original="results/main15_v2/jev/libero_object_swap/task_${task}_seed_0/result.json"
    output="$RESULTS_ROOT/jev/libero_object_swap/task_${task}_seed_0/result.json"
    if [ -f "$original" ] || [ -f "$output" ]; then
        echo "Preserving completed task $task; skip."
        continue
    fi
    MODELS=jev SUITES=libero_object_swap TASKS="$task" \
        RESULTS_ROOT="$RESULTS_ROOT" MAX_DECISIONS=15 \
        bash "$ROOT/run_typed_choice_node02.sbatch"
done
