#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=130G
#SBATCH --time=12:00:00
#SBATCH --nice=5000
#SBATCH --job-name=libero-success578
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
ROOT=/public/home/sunyihan/rpent_libero_eval
SOURCE=${SUCCESS578_SOURCE:?absolute source required}
PREP=${SUCCESS578_PREP:?absolute preparation required}
COHORT=truth
PART=${SLURM_ARRAY_TASK_ID:-0}
PLAN="$PREP/${COHORT}_part${PART}.json"
export PYTHONPATH="$PREP:$SOURCE" LIBERO_CONFIG_PATH="$ROOT/runtime_config"
export LIBEROPRO_DATASET_PATH="$ROOT/../liberopro_hf/c86fc3b8293185a6f373677018ff3e37f8391602"
export LIBERO_TYPE=standard
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
CHECKOUT="$PREP/launcher_preflight/${COHORT}_part${PART}"
if [[ "${SUCCESS578_PREFLIGHT_ONLY:-0}" != 1 ]]; then
 CHECKOUT="$ROOT/results/harness_v5/success578_sim_truth_20261007/job${SLURM_ARRAY_JOB_ID}/part${PART}"
fi
mkdir -p "$CHECKOUT"
"$ROOT/.venv/bin/python" - "$PLAN" "$PREP" "$SOURCE" <<'PY'
import hashlib,json,sys
from pathlib import Path
p,prep,s=map(Path,sys.argv[1:])
assert p.is_absolute() and prep.is_absolute() and s.is_absolute()
x=json.loads(p.read_text()); index=json.loads((prep/'manifest.json').read_text())
assert x['behavior_frozen'] is False and x['training_allowed'] is False
assert x['source_path']==str(s) and x['source_commit']=='5da67d19fe8dde8564e06c39266bb1fedc330d2a'
for r in [*index['files'],*index['references'],*index['source_snapshot']['files'],index['source_snapshot']['archive']]:
 f=Path(r['path']); assert f.is_absolute() and hashlib.sha256(f.read_bytes()).hexdigest()==r['sha256'],str(f)
assert len(x['episodes']) == 5
for name in ('harness_v5_eval.py','robots/libero/v5_state.py'):
 assert (s/name).is_file()
assert (prep/'v5_batch_eval.py').is_file()
batch_ref=index['batch_runner'];assert hashlib.sha256(Path(batch_ref['path']).read_bytes()).hexdigest()==batch_ref['sha256']
for r in index.get('runtime_supplement',[]):
 f=Path(r['path']);assert hashlib.sha256(f.read_bytes()).hexdigest()==r['sha256'],str(f)
root=Path('/public/home/sunyihan/rpent_libero_eval');rd=root.parent/'rd_instruction_20260923'
for resource in (root/'.venv/bin/python', root/'runtime_config/config.yaml', root/'assets/pi05', root/'assets/sam3/sam3.pt',
                 rd/'v5r_20261001/v5_main_job3088/candidate_step750/pytorch_model.bin',
                 rd/'v5r_20261001/qualified_service_sources_bf097673/v5r_server.py',
                 rd/'v5_models/qwen3_5_4b_851bf6e8/config.json', rd/'v5r_20261001/package3072/parallel_schema.py'):
 assert resource.exists(),str(resource)
PY
PYTHONPATH="$PREP:$SOURCE" "$ROOT/.venv/bin/python" - <<'IMPORTS'
from transformers import AutoTokenizer
from robots.libero.robot_spec import _init_runtime
from robots.libero.toolkit import LiberoToolkit
from robots.libero.v5_env_client import V5SkillEnvClient
from robots.libero.v5_runtime import MeasuredScene, V5Executor
from rpent.dashboard.events import NullDashboardEventSink
from rpent.memory import MemoryManager
from typed_choice_eval import ChoiceScorer
from robots.libero.v5_systemone import score
IMPORTS
cd /tmp
"$ROOT/.venv/bin/python" "$SOURCE/scripts/preflight_v5_runtime536_smoke.py" --assets "$PLAN" --output "$CHECKOUT/assets.json"
if [[ "${SUCCESS578_PREFLIGHT_ONLY:-0}" == 1 ]]; then exit 0; fi
cd "$SOURCE"
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false
ENDPOINT=unused
if [[ "$COHORT" == truth ]]; then
 RD=/public/home/sunyihan/rd_instruction_20260923
 SERVICE="$RD/v5r_20261001/qualified_service_sources_bf097673"
 export V5R_BASE="$RD/v5_models/qwen3_5_4b_851bf6e8"
 export V5R_CHECKPOINT="$RD/v5r_20261001/v5_main_job3088/candidate_step750/pytorch_model.bin"
 export V5R_PACKAGE="$RD/v5r_20261001/package3072"
 export V5R_TOKEN_LIMIT=3072 V5R_EXPERIMENTAL_PREFIX_FORK=0
 unset V5R_CALIBRATION DECIDER_API_KEY
 PORT=$("$ROOT/.venv/bin/python" -c 'from rpent.utils.daemon import pick_free_port; print(pick_free_port())')
 PP=/public/home/sunyihan/.cache/uv/archive-v0/9k-b95Vkiz_wwIuJtk55f:/public/home/sunyihan/.cache/uv/archive-v0/axVQBChkwnIeMnJgrBhUx:/public/home/sunyihan/.cache/uv/archive-v0/LO_N6_FRg6WZCTC8gbXPA:/public/home/sunyihan/.cache/uv/archive-v0/8M_o4LbB10dqYO670ydE2:/public/home/sunyihan/.cache/uv/archive-v0/NVAZG0lqLoni-_KahYBkO:/public/home/sunyihan/.cache/uv/archive-v0/q1XAbNv0jquFac-o3fXuk:/public/home/sunyihan/.cache/uv/archive-v0/DI6MNFXwF3R-gcgWs4wlo:/public/home/sunyihan/robot_decider/runtime/.venv/lib/python3.12/site-packages
 PYTHONPATH="$SERVICE:$PP" /public/home/sunyihan/robot_decider/runtime/.venv/bin/python -m uvicorn v5r_server:app --host 127.0.0.1 --port "$PORT" > "$CHECKOUT/model_service.log" 2>&1 &
 service_pid=$!
 trap 'kill "$service_pid" 2>/dev/null || true; wait "$service_pid" 2>/dev/null || true' EXIT
 "$ROOT/.venv/bin/python" - "$PORT" "$service_pid" "$CHECKOUT" <<'HEALTH'
import json,os,sys,time
from pathlib import Path
from urllib.request import urlopen
port,pid,out=int(sys.argv[1]),int(sys.argv[2]),Path(sys.argv[3]);deadline=time.monotonic()+600
while True:
 try:
  with urlopen(f'http://127.0.0.1:{port}/health',timeout=5) as r:h=json.load(r)
 except (OSError,ValueError):
  os.kill(pid,0)
  if time.monotonic()>deadline:raise RuntimeError('Step750 service startup timed out')
  time.sleep(2);continue
 assert h['revision']=='b226f57a8f7ba32b5e58453182cfe47e0434812a8edbea6b003d9bad36ce4bcb',h
 assert h['max_context_tokens']==3072 and h['model'].endswith('/candidate_step750/pytorch_model.bin'),h
 (out/'model_identity.json').write_text(json.dumps(h,indent=2)+'\n');break
HEALTH
 ENDPOINT="http://127.0.0.1:$PORT"
fi
export PYTHONPATH="$PREP:$SOURCE"
PROVIDER=systemone
if [[ "$COHORT" == expert ]]; then PROVIDER=oracle; fi
"$ROOT/.venv/bin/python" -u "$PREP/run_original_success578.py" --batch-runner "$PREP/v5_batch_eval.py" --provider "$PROVIDER" --choice-endpoint "$ENDPOINT" --manifest "$PLAN" --choice-package /public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a --pause-marker "$CHECKOUT/PAUSE_REQUESTED" --output-dir "$CHECKOUT/probe"
