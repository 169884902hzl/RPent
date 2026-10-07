#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=02:00:00
#SBATCH --array=0-7%8
#SBATCH --nice=1000
#SBATCH --job-name=libero-moka-transfer
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
MOKA_TRANSFER_ROOT=/public/home/sunyihan/rpent_libero_eval
MOKA_TRANSFER_SOURCE=${MOKA_TRANSFER_SOURCE:?immutable source required}
MOKA_TRANSFER_MANIFEST=${MOKA_TRANSFER_MANIFEST:?visited-state smoke manifest required}
MOKA_TRANSFER_MANIFEST_SHA=${MOKA_TRANSFER_MANIFEST_SHA:?registered manifest SHA required}
export PYTHONPATH="$MOKA_TRANSFER_SOURCE:$MOKA_TRANSFER_ROOT" LIBERO_TYPE=standard PYTHONDONTWRITEBYTECODE=1
MOKA_TRANSFER_PREP=$(dirname "$MOKA_TRANSFER_MANIFEST")
export PYTHONPATH="$MOKA_TRANSFER_PREP:$MOKA_TRANSFER_SOURCE:$MOKA_TRANSFER_ROOT"
export LIBERO_CONFIG_PATH="$MOKA_TRANSFER_ROOT/runtime_config"
export PI05_CHECKPOINT_PATH="$MOKA_TRANSFER_ROOT/assets/pi05" SAM3_CHECKPOINT_PATH="$MOKA_TRANSFER_ROOT/assets/sam3/sam3.pt"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export MUJOCO_GL=egl PYOPENGL_PLATFORM=egl
MOKA_TRANSFER_BASE="$MOKA_TRANSFER_ROOT/results/harness_v5/moka_transfer_confirmation_prep_CPU_20261007"
"$MOKA_TRANSFER_ROOT/.venv/bin/python" - "$MOKA_TRANSFER_MANIFEST" "$MOKA_TRANSFER_MANIFEST_SHA" "$MOKA_TRANSFER_SOURCE" <<'PY'
import hashlib,json
from pathlib import Path
import sys
m,s=Path(sys.argv[1]),Path(sys.argv[3])
if not m.is_absolute() or not s.is_absolute() or hashlib.sha256(m.read_bytes()).hexdigest()!=sys.argv[2]:
    raise ValueError('Absolute pinned manifest/source required')
p=json.loads(m.read_text()); identity=p['source_snapshot']
if (p['qualification_authorized'] is not False or p['new_training_rows']!=0
        or p['selection']['analysis_role']!='development_visited_state_smoke'
        or len(p['cases'])!=10 or s.resolve()!=Path(identity['path']).resolve()):
    raise ValueError('Only the registered ten visited development states are authorized')
for r in [*identity['files'],identity['archive'],p['producer'],*p['producer_dependencies']]:
    f=Path(r['path'])
    if not f.is_absolute() or hashlib.sha256(f.read_bytes()).hexdigest()!=r['sha256']:
        raise ValueError(f'Pinned reference changed: {f}')
supplement=m.parent / 'typed_choice_eval.py'
if not supplement.is_file():
    raise ValueError('registered typed_choice_eval.py supplement missing')
PY
EXCLUDED_CASE_NAMES=$("$MOKA_TRANSFER_ROOT/.venv/bin/python" - "$MOKA_TRANSFER_MANIFEST" "$0" <<'PY'
import hashlib,json,os,sys
from pathlib import Path
names=[]
file=os.environ.get("MOKA_TRANSFER_EXCLUDE_CASES_FILE")
if file:
    path=Path(file)
    if not path.is_absolute():
        raise ValueError("MOKA_TRANSFER_EXCLUDE_CASES_FILE must be absolute")
    values=json.loads(path.read_text())
    if not isinstance(values,list):
        raise ValueError("exclusion file must contain a JSON list of case names")
    names.extend(values)
for key in ("MOKA_TRANSFER_EXCLUDE_CASE_NAMES", "MOKA_TRANSFER_EXCLUDE_CASE_NAME"):
    if os.environ.get(key):
        names.extend(name.strip() for name in os.environ[key].split(","))
if any(not isinstance(name,str) or not name or "\n" in name or "\r" in name for name in names):
    raise ValueError("excluded case names must be nonempty single-line strings")
manifest=Path(sys.argv[1]); plan=json.loads(manifest.read_text())
registered={case["name"] for case in plan["cases"]}
unknown=set(names)-registered
if unknown:
    raise ValueError(f"excluded cases not registered: {sorted(unknown)}")
if os.environ.get("MOKA_TRANSFER_STARTUP_PREFLIGHT") != "1" and os.environ.get("MOKA_TRANSFER_PREFLIGHT_ONLY") != "1":
    contract_path=Path(os.environ["MOKA_TRANSFER_STARTUP_CONTRACT"])
    if not contract_path.is_absolute():
        raise ValueError("MOKA_TRANSFER_STARTUP_CONTRACT must be absolute")
    data=contract_path.read_bytes()
    if hashlib.sha256(data).hexdigest() != os.environ["MOKA_TRANSFER_STARTUP_CONTRACT_SHA"]:
        raise ValueError("startup contract SHA changed")
    contract=json.loads(data)
    identity={
        "manifest_sha256":hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "source_snapshot_sha256":hashlib.sha256(json.dumps(plan["source_snapshot"],sort_keys=True,separators=(",",":")).encode()).hexdigest(),
        "launcher_sha256":hashlib.sha256(Path(sys.argv[2]).read_bytes()).hexdigest(),
    }
    if (contract.get("status") != "pass" or int(contract.get("requested_controls",0)) <= 0
            or any(contract.get(key) != value for key,value in identity.items())):
        raise ValueError("startup contract does not qualify this manifest/source/launcher")
    if contract.get("case_name") not in set(names):
        raise ValueError("startup preflight case must be excluded from formal shards")
for name in dict.fromkeys(names):
    print(name)
PY
)
FORMAL_CASE_ARGS=()
if [[ -n "$EXCLUDED_CASE_NAMES" ]]; then
  while IFS= read -r CASE_NAME; do
    FORMAL_CASE_ARGS+=(--exclude-case-name "$CASE_NAME")
  done <<< "$EXCLUDED_CASE_NAMES"
fi
cd /tmp
if [[ "${MOKA_TRANSFER_PREFLIGHT_ONLY:-0}" == 1 ]]; then
  exec "$MOKA_TRANSFER_ROOT/.venv/bin/python" "$MOKA_TRANSFER_SOURCE/scripts/v5_probe_preflight.py" \
    --manifest "$MOKA_TRANSFER_MANIFEST" --shard-index "${SLURM_ARRAY_TASK_ID:-0}" --shards 8 --states
fi

if [[ "${MOKA_TRANSFER_STARTUP_PREFLIGHT:-0}" == 1 ]]; then
  PREFLIGHT_CASE=$("$MOKA_TRANSFER_ROOT/.venv/bin/python" - "$MOKA_TRANSFER_MANIFEST" <<'PY'
import json,os,sys
from pathlib import Path
plan=json.loads(Path(sys.argv[1]).read_text())
if len(plan.get("cases", [])) < 1:
    raise SystemExit("registered manifest has no cases")
name=os.environ.get("MOKA_TRANSFER_PREFLIGHT_CASE_NAME",plan["cases"][0]["name"])
if name not in {case["name"] for case in plan["cases"]}:
    raise SystemExit("startup case must belong to the registered manifest")
print(name)
PY
  )
  PREFLIGHT_OUT="$MOKA_TRANSFER_BASE/startup_preflight/${SLURM_JOB_ID:-manual}"
  mkdir -p "$PREFLIGHT_OUT"
  set +e
  "$MOKA_TRANSFER_ROOT/.venv/bin/python" -u "$MOKA_TRANSFER_SOURCE/scripts/probe_v5_moka_transfer_public_20261007.py" \
    --manifest "$MOKA_TRANSFER_MANIFEST" --case-name "$PREFLIGHT_CASE" \
    --shard-index 0 --shards 1 --output "$PREFLIGHT_OUT/probe" \
    > "$PREFLIGHT_OUT/runner.stdout.log" 2> "$PREFLIGHT_OUT/runner.stderr.log"
  PREFLIGHT_RC=$?
  set -e
  "$MOKA_TRANSFER_ROOT/.venv/bin/python" - "$PREFLIGHT_OUT/probe" "$PREFLIGHT_RC" "$MOKA_TRANSFER_MANIFEST" "$0" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1]); rc=int(sys.argv[2])
ledger=root/"episodes.jsonl"
audit=root/"startup_dependency_audit.json"
if not ledger.is_file():
    raise SystemExit("startup preflight produced no episodes.jsonl")
if not audit.is_file():
    raise SystemExit("startup preflight produced no dependency audit")
dep=json.loads(audit.read_text()); dep_path=Path(dep["path"])
if not dep_path.is_file():
    raise SystemExit(f"dependency audit path missing: {dep_path}")
import hashlib
if hashlib.sha256(dep_path.read_bytes()).hexdigest() != dep["sha256"]:
    raise SystemExit("dependency audit hash changed during preflight")
rows=[json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
if len(rows) != 1:
    raise SystemExit(f"startup preflight expected one episode, found {len(rows)}")
row=rows[0]; result=row.get("result",{})
controls=row.get("server_chunk_execution") or {}
if result.get("status") in ("startup", "startup_error") or result.get("infrastructure_failure") or row.get("case_had_infrastructure_failure"):
    raise SystemExit("startup preflight hit startup/infrastructure failure")
if int(controls.get("requested_controls", 0)) <= 0:
    raise SystemExit("startup preflight produced no requested physical controls")
if rc:
    raise SystemExit(f"startup preflight runner exited {rc}")
manifest=Path(sys.argv[3]); plan=json.loads(manifest.read_text())
(root/"contract.json").write_text(json.dumps({
    "status":"pass", "case_name":row["case"]["name"], "case":row["case"],
    "result_status":result.get("status"), "requested_controls":int(controls["requested_controls"]),
    "manifest_sha256":hashlib.sha256(manifest.read_bytes()).hexdigest(),
    "source_snapshot_sha256":hashlib.sha256(json.dumps(plan["source_snapshot"],sort_keys=True,separators=(",",":")).encode()).hexdigest(),
    "launcher_sha256":hashlib.sha256(Path(sys.argv[4]).read_bytes()).hexdigest(),
}, indent=2)+"\n")
PY
  exit 0
fi
MOKA_TRANSFER_OUT="$MOKA_TRANSFER_BASE/smoke10/job${SLURM_ARRAY_JOB_ID}/part${SLURM_ARRAY_TASK_ID}"
mkdir -p "$MOKA_TRANSFER_OUT"
"$MOKA_TRANSFER_ROOT/.venv/bin/python" "$MOKA_TRANSFER_SOURCE/scripts/v5_probe_preflight.py" \
  --manifest "$MOKA_TRANSFER_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 8 --states > "$MOKA_TRANSFER_OUT/preflight.json"
set +e
"$MOKA_TRANSFER_ROOT/.venv/bin/python" -u "$MOKA_TRANSFER_SOURCE/scripts/probe_v5_moka_transfer_public_20261007.py" \
  "${FORMAL_CASE_ARGS[@]}" \
  --manifest "$MOKA_TRANSFER_MANIFEST" --shard-index "$SLURM_ARRAY_TASK_ID" --shards 8 --output "$MOKA_TRANSFER_OUT/probe"
RUN_RC=$?
set -e
"$MOKA_TRANSFER_ROOT/.venv/bin/python" - "$MOKA_TRANSFER_OUT/probe" "$RUN_RC" <<'PY'
import json,sys
from pathlib import Path
root=Path(sys.argv[1]); rc=int(sys.argv[2])
ledger=root/"episodes.jsonl"
audit=root/"startup_dependency_audit.json"
if not ledger.is_file():
    raise SystemExit("formal run produced no episodes.jsonl")
if not audit.is_file():
    raise SystemExit("formal run produced no dependency audit")
dep=json.loads(audit.read_text()); dep_path=Path(dep["path"])
if not dep_path.is_file():
    raise SystemExit(f"dependency audit path missing: {dep_path}")
import hashlib
if hashlib.sha256(dep_path.read_bytes()).hexdigest() != dep["sha256"]:
    raise SystemExit("dependency audit hash changed during formal run")
rows=[json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
if not rows:
    raise SystemExit("formal run produced an empty episodes.jsonl")
infra=[]
for row in rows:
    result=row.get("result",{})
    if (result.get("status") in ("startup", "startup_error")
            or result.get("infrastructure_failure")
            or row.get("case_had_infrastructure_failure")):
        infra.append(row.get("case", {}).get("name", "unknown"))
if infra:
    print("startup/infrastructure failures: " + ",".join(infra), file=sys.stderr)
    raise SystemExit(2)
if rc:
    raise SystemExit(rc)
missing_controls=[row.get("case", {}).get("name", "unknown") for row in rows
                  if int((row.get("server_chunk_execution") or {}).get("requested_controls", 0)) <= 0]
if missing_controls:
    print("no requested physical controls: " + ",".join(missing_controls), file=sys.stderr)
    raise SystemExit(2)
(root/"contract.json").write_text(json.dumps({"status":"pass","episodes":len(rows)}, indent=2)+"\n")
PY
