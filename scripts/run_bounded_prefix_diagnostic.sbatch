#!/bin/bash
#SBATCH --job-name=rd-bounded-prefix-diagnostic
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --nice=500
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%j.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE=${SOURCE:?absolute source snapshot required}
CHOICES=${CHOICES:?absolute choices path required}
OUT=${OUT:?fresh absolute output path required}
SUITE=${SUITE:?original suite required}
TASK=${TASK:?task index required}
SEED=${SEED:?original init required}
THROUGH=${THROUGH:?last prefix row required}
export PYTHONPATH="$SOURCE"
export MUJOCO_GL=egl
export PYOPENGL_PLATFORM=egl
export LIBERO_TYPE=standard
export LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=4
cd "$SOURCE"
test -f "$CHOICES"
test ! -e "$OUT"
# Refuse incomplete prefixes before the GPU-backed simulator is created.
"$ROOT/.venv/bin/python" - "$CHOICES" "$THROUGH" <<'PY'
import json, sys
from pathlib import Path
from scripts.probe_bounded_prefix_diagnostic import prefix_controls
path = Path(sys.argv[1]).resolve(strict=True)
assert path.is_absolute()
prefix_controls([json.loads(line) for line in path.read_text().splitlines()], int(sys.argv[2]))
PY
exec "$ROOT/.venv/bin/python" -u -m scripts.probe_bounded_prefix_diagnostic \
    --choices "$CHOICES" --suite "$SUITE" --task "$TASK" --seed "$SEED" \
    --through "$THROUGH" --output "$OUT"
