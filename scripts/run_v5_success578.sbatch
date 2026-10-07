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
LAUNCHER="$0"
STARTUP=${SUCCESS578_STARTUP_PREFLIGHT:-0}
STARTUP_CONTRACT=${SUCCESS578_STARTUP_CONTRACT:-}
export PYTHONPATH="$SOURCE/scripts:$SOURCE" LIBERO_CONFIG_PATH="$ROOT/runtime_config" PYTHONDONTWRITEBYTECODE=1
export LIBEROPRO_DATASET_PATH="$ROOT/../liberopro_hf/c86fc3b8293185a6f373677018ff3e37f8391602"
export LIBERO_TYPE=standard
export PI05_CHECKPOINT_PATH="$ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
CHECKOUT="$PREP/launcher_preflight/${COHORT}_part${PART}"
if [[ "${SUCCESS578_PREFLIGHT_ONLY:-0}" != 1 ]]; then
 if [[ "$STARTUP" == 1 ]]; then
  CHECKOUT="$ROOT/results/harness_v5/success578_sim_truth_20261008/startup_preflight/job${SLURM_ARRAY_JOB_ID:-${SLURM_JOB_ID:-manual}}/part${PART}"
 else
  CHECKOUT="$ROOT/results/harness_v5/success578_sim_truth_20261008/job${SLURM_ARRAY_JOB_ID:?array job ID required}/part${PART}"
 fi
fi
mkdir -p "$CHECKOUT"
"$ROOT/.venv/bin/python" - "$PLAN" "$PREP" "$SOURCE" "$LAUNCHER" <<'PY'
import hashlib,json,sys
from pathlib import Path
p,prep,s,launcher=map(Path,sys.argv[1:])
assert p.is_absolute() and prep.is_absolute() and s.is_absolute()
x=json.loads(p.read_text()); index=json.loads((prep/'manifest.json').read_text())
assert x['behavior_frozen'] is False and x['training_allowed'] is False
assert x['source_path']==str(s)==index['source_path']==index['source_snapshot']['path']
assert x['source_commit']==index['source_commit']
for r in [*index['files'],*index['references'],*index['source_snapshot']['files'],index['source_snapshot']['archive']]:
 f=Path(r['path']); assert f.is_absolute() and hashlib.sha256(f.read_bytes()).hexdigest()==r['sha256'],str(f)
assert 1 <= len(x['episodes']) <= 25
assert x["libero_type"] == "standard" and x["cohort"] == "truth"
assert x["budget"]["success_prediction_diagnostic"] is True and not x["budget"].get("success_top3_v1", False)
assert all(e["suite"] in ("libero_spatial", "libero_object", "libero_goal", "libero_10") and 0 <= e["task"] < 10 for e in x["episodes"])
assert x['cohort']==sys.argv[1].split('/')[-1].split('_part')[0]
for name in ('harness_v5_eval.py','robots/libero/v5_state.py', 'typed_choice_eval.py',
             'v5_batch_eval.py','scripts/preflight_v5_runtime536_smoke.py',
             'scripts/run_original_success578.py','scripts/original_success578_server.py'):
 assert (s/name).is_file()
batch_ref=index['batch_runner'];assert Path(batch_ref['path']).resolve()==(s/'v5_batch_eval.py').resolve()
assert hashlib.sha256(Path(batch_ref['path']).read_bytes()).hexdigest()==batch_ref['sha256']
if 'launcher' in index:
 assert hashlib.sha256(launcher.read_bytes()).hexdigest()==index['launcher']['sha256']
for r in index.get('runtime_supplement',[]):
 f=Path(r['path']);assert hashlib.sha256(f.read_bytes()).hexdigest()==r['sha256'],str(f)
root=Path('/public/home/sunyihan/rpent_libero_eval');rd=root.parent/'rd_instruction_20260923'
for resource in (root/'.venv/bin/python', root/'runtime_config/config.yaml', root/'assets/pi05', root/'assets/sam3/sam3.pt',
                 rd/'v5r_20261001/v5_main_job3088/candidate_step750/pytorch_model.bin',
                 rd/'v5r_20261001/qualified_service_sources_bf097673/v5r_server.py',
                 rd/'v5_models/qwen3_5_4b_851bf6e8/config.json', rd/'v5r_20261001/package3072/parallel_schema.py'):
 assert resource.exists(),str(resource)
PY
PYTHONPATH="$SOURCE/scripts:$SOURCE" "$ROOT/.venv/bin/python" - "$SOURCE" <<'IMPORTS'
import sys
from pathlib import Path
from transformers import AutoTokenizer
from robots.libero.robot_spec import _init_runtime
from robots.libero.toolkit import LiberoToolkit
from robots.libero.v5_env_client import V5SkillEnvClient
from robots.libero.v5_runtime import MeasuredScene, V5Executor
from rpent.dashboard.events import NullDashboardEventSink
from rpent.memory import MemoryManager
from typed_choice_eval import ChoiceScorer
from robots.libero.v5_systemone import score
from original_success578_server import PassiveLabels
from run_original_success578 import export_pairs
import typed_choice_eval
assert Path(typed_choice_eval.__file__).resolve()==Path(sys.argv[1]).resolve()/'typed_choice_eval.py'
IMPORTS
cd /tmp
"$ROOT/.venv/bin/python" "$SOURCE/scripts/preflight_v5_runtime536_smoke.py" --assets "$PLAN" --output "$CHECKOUT/assets.json"
if [[ "${SUCCESS578_PREFLIGHT_ONLY:-0}" == 1 ]]; then exit 0; fi
"$ROOT/.venv/bin/python" - "$PLAN" "$PREP" "$SOURCE" "$LAUNCHER" "$CHECKOUT" "$STARTUP" "$STARTUP_CONTRACT" <<'RUN_PLAN'
import hashlib,json,sys
from pathlib import Path
plan,prep,source,launcher,out=map(Path,sys.argv[1:6])
startup,contract_path=sys.argv[6:8]
payload=json.loads(plan.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
identity={"cohort":payload["cohort"],"source_path":str(source),
          "source_commit":payload["source_commit"],
          "manifest_index_sha256":sha(prep/"manifest.json"),
          "launcher_sha256":sha(launcher)}
if startup=="1":
 payload["episodes"]=payload["episodes"][:1]
else:
 if not contract_path:
  raise SystemExit("formal array requires SUCCESS578_STARTUP_CONTRACT from the same launcher/source/cohort")
 contract=json.loads(Path(contract_path).resolve(strict=True).read_text())
 if contract.get("status")!="pass" or any(contract.get(k)!=v for k,v in identity.items()):
  raise SystemExit("startup contract differs from this launcher/source/cohort")
 if not contract.get("physical_actions"):
  raise SystemExit("startup contract has no actual physical execution evidence")
 for name in ("episodes", "choices", "pairing_manifest", "private_action_labels"):
  record=contract[name]; file=Path(record["path"])
  if not file.is_absolute() or sha(file)!=record["sha256"]:
   raise SystemExit("startup physical evidence changed: "+str(file))
 completed=contract["episode"]
 # Preserve the completed startup episode as part of the interim cohort.
 # Remove only its exact identity from the formal shard, without rerunning it.
 payload["episodes"]=[e for e in payload["episodes"] if e!=completed]
 if not payload["episodes"]:
  raise SystemExit("formal shard has no episodes after preserving startup result")
payload["launcher_execution_identity"]=identity
payload["parent_plan"]={"path":str(plan),"sha256":sha(plan)}
path=out/"runtime_plan.json"
if path.exists():
 raise SystemExit("runtime plan already exists; keep prior attempt and use a new job")
path.write_text(json.dumps(payload,indent=2)+"\n")
RUN_PLAN
PLAN="$CHECKOUT/runtime_plan.json"
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
export PYTHONPATH="$SOURCE/scripts:$SOURCE"
PROVIDER=systemone
if [[ "$COHORT" == expert ]]; then PROVIDER=oracle; fi
set +e
"$ROOT/.venv/bin/python" -u "$SOURCE/scripts/run_original_success578.py" --batch-runner "$SOURCE/v5_batch_eval.py" --model-identity "$CHECKOUT/model_identity.json" --provider "$PROVIDER" --choice-endpoint "$ENDPOINT" --manifest "$PLAN" --choice-package /public/home/sunyihan/rd_instruction_20260923/v31_package_decider_2048_socket_20260925a --pause-marker "$CHECKOUT/PAUSE_REQUESTED" --output-dir "$CHECKOUT/probe"
RUN_RC=$?
set -e
"$ROOT/.venv/bin/python" - "$PLAN" "$CHECKOUT/probe" "$RUN_RC" "$STARTUP" <<'EXIT_CONTRACT'
import hashlib,json,sys
from pathlib import Path
plan,output=map(Path,sys.argv[1:3]);rc=int(sys.argv[3]);startup=sys.argv[4]=="1"
ledger=output/"episodes.jsonl"
if not ledger.is_file():
 raise SystemExit("runner produced no episodes ledger")
rows=[json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
if not rows:
 raise SystemExit("runner produced no attempted episode")
infra=[r["episode"] for r in rows if r["result"].get("status") in ("startup","startup_error")
       or r["result"].get("termination_category")=="startup_error"
       or r["result"].get("infrastructure_failure")]
if infra:
 print(json.dumps({"startup_or_infrastructure_errors":infra}),file=sys.stderr)
 raise SystemExit(2)
if rc:
 raise SystemExit(rc)
pair_path=output/"pairing_manifest.json"
if not pair_path.is_file():
 raise SystemExit("passive runner produced no explicit same-run pairing manifest")
pairs=json.loads(pair_path.read_text())
if startup:
 if len(rows)!=1:
  raise SystemExit("startup preflight must preserve exactly one attempted episode")
 result=rows[0]["result"]
 if not (result.get("status")=="completed" or result.get("status")=="error"
         and result.get("termination_category")=="no_legal_candidate"):
  raise SystemExit("startup preflight contains an unresolved runtime error")
 row=rows[0];choices=Path(row["output_dir"])/"choices.jsonl"
 decisions=[json.loads(line) for line in choices.read_text().splitlines() if line.strip()]
 physical=[]
 for decision in decisions:
  receipt=decision.get("receipt",{})
  chunks=int(receipt.get("chunks",0) or 0)
  chunks=max(chunks,int(receipt.get("primitive_result",{}).get("chunks_used",0) or 0))
  steps=sum(int(e.get("steps_used",0) or 0) for e in decision.get("motion_evidence",[]))
  if chunks>0 or steps>0:
   physical.append({"decision":decision["decision"],"selected":decision["selected"],
                    "executed_chunks":chunks,"executed_motion_steps":steps})
 if not physical:
  raise SystemExit("startup preflight produced no executed physical action")
 labels=Path(row["output_dir"])/"private_action_labels.jsonl"
 label_rows=[json.loads(line) for line in labels.read_text().splitlines() if line.strip()]
 if not any(r.get("physical_control_steps",0)>0 for r in label_rows):
  raise SystemExit("passive sidecar has no actual control-step evidence")
 if pairs["counts"]["actions"]+pairs["counts"]["finish"]<1 or pairs["counts"]["prediction_unknown"]:
  raise SystemExit("startup has no same-run pre-action probability/choice/label links")
 payload=json.loads(plan.read_text())
 contract={**payload["launcher_execution_identity"],"status":"pass",
           "episode":row["episode"],"parent_plan":payload["parent_plan"],
           "physical_actions":physical,"result_status":row["result"]["status"],
           "result_termination_category":row["result"].get("termination_category"),
           "startup_only_not_skill_qualification":True,
           "episodes":{"path":str(ledger),"sha256":hashlib.sha256(ledger.read_bytes()).hexdigest()},
           "choices":{"path":str(choices),"sha256":hashlib.sha256(choices.read_bytes()).hexdigest()},
           "pairing_manifest":{"path":str(pair_path),"sha256":hashlib.sha256(pair_path.read_bytes()).hexdigest()},
           "private_action_labels":{"path":str(labels),"sha256":hashlib.sha256(labels.read_bytes()).hexdigest()}}
 (output.parent/"startup_contract.json").write_text(json.dumps(contract,indent=2)+"\n")
EXIT_CONTRACT
