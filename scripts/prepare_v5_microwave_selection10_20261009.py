"""Run the repaired public microwave endpoint on ten visited original cases."""

import copy
import hashlib
import json
from pathlib import Path

from prepare_expert_remote_resume_20261008 import read_pinned, ref


ROOT = Path("/public/home/sunyihan/rpent_libero_eval")
TEMPLATE = ROOT / "results/harness_v5/microwave_verified_view_20261009_r1/stop_verified48.json"
TEMPLATE_SHA = "e007306564e5e249accf2658d06a8e1100296adfd4fb2ea7f0d3d872beeb6d95"
PARENT = ROOT / "results/harness_v5/microwave571_public_parent_CPU_20261006/preparation/registered/microwave_public_parent_original10.json"
PARENT_SHA = "f9a8b3532b169c0cf93e3d78445e11e96c8beeb343ec36b76ad96c491b9a2296"
OUTPUT = ROOT / "results/harness_v5/microwave_verified_selection10_20261009_r1"

LAUNCHER = '''#!/usr/bin/env bash
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=90G
#SBATCH --time=03:00:00
#SBATCH --job-name=microwave-selection10
#SBATCH --output=/public/home/sunyihan/rpent_libero_eval/results/slurm-%A_%a.log
set -euo pipefail
: "${MICROWAVE_SELECTION_INDEX:?absolute pinned index required}"
: "${MICROWAVE_SELECTION_INDEX_SHA:?index SHA required}"
MICROWAVE_SELECTION_PY=/public/home/sunyihan/rpent_libero_eval/.venv/bin/python
mapfile -t MICROWAVE_SELECTION_ARGS < <("$MICROWAVE_SELECTION_PY" - "$MICROWAVE_SELECTION_INDEX" "$MICROWAVE_SELECTION_INDEX_SHA" "$0" <<'PY'
import hashlib,json,os,sys
from pathlib import Path
index=Path(sys.argv[1])
if not index.is_absolute() or hashlib.sha256(index.read_bytes()).hexdigest()!=sys.argv[2]:
    raise ValueError("selection index identity changed")
plan=json.loads(index.read_text()); item=plan["plans"][int(os.environ.get("SLURM_ARRAY_TASK_ID","0"))]
for ref in (item["manifest"],plan["launcher"],plan["parent_manifest"],plan["template_manifest"]):
    p=Path(ref["path"])
    if not p.is_absolute() or hashlib.sha256(p.read_bytes()).hexdigest()!=ref["sha256"]:
        raise ValueError("pinned selection dependency changed: "+str(p))
if os.environ.get("MICROWAVE_CPU_ONLY")!="1" and os.environ.get("MICROWAVE_SELECTION_STARTUP")!="1":
    p=Path(os.environ["MICROWAVE_SELECTION_STARTUP_CONTRACT"])
    if not p.is_absolute(): raise ValueError("absolute startup contract required")
    contract=json.loads(p.read_text())
    if (contract["status"]!="pass" or contract["index_sha256"]!=sys.argv[2]
            or contract["wrapper_sha256"]!=hashlib.sha256(Path(sys.argv[3]).read_bytes()).hexdigest()
            or int(contract["requested_controls"])<=0 or item["index"]==contract["index"]):
        raise ValueError("startup contract does not qualify this selection or repeats startup")
print(plan["source"]); print(item["manifest"]["path"]); print(item["manifest"]["sha256"])
print(plan["launcher"]["path"]); print(plan["physical_root"])
PY
)
if [[ ${#MICROWAVE_SELECTION_ARGS[@]} != 5 ]]; then exit 2; fi
export MICROWAVE_SOURCE="${MICROWAVE_SELECTION_ARGS[0]}"
export MICROWAVE_PLAN="${MICROWAVE_SELECTION_ARGS[1]}" MICROWAVE_PLAN_SHA="${MICROWAVE_SELECTION_ARGS[2]}"
export MICROWAVE_OUTPUT="${MICROWAVE_SELECTION_ARGS[4]}/job${SLURM_ARRAY_JOB_ID:-manual}/part${SLURM_ARRAY_TASK_ID:-0}"
bash "${MICROWAVE_SELECTION_ARGS[3]}"
if [[ "${MICROWAVE_CPU_ONLY:-0}" == 1 ]]; then exit 0; fi
"$MICROWAVE_SELECTION_PY" - "$MICROWAVE_OUTPUT" "$MICROWAVE_SELECTION_INDEX_SHA" "$0" <<'PY'
import hashlib,json,os,sys
from pathlib import Path
root=Path(sys.argv[1]); physical=json.loads((root/"physical_startup_contract.json").read_text())
if physical["status"]!="pass" or physical["requested_controls"]<=0:
    raise SystemExit("startup_error: physical contract failed")
if os.environ.get("MICROWAVE_SELECTION_STARTUP")=="1":
    contract={**physical,"index":int(os.environ.get("SLURM_ARRAY_TASK_ID","0")),
        "index_sha256":sys.argv[2],"wrapper_sha256":hashlib.sha256(Path(sys.argv[3]).read_bytes()).hexdigest(),
        "episodes":{"path":str(root/"episodes.jsonl"),"sha256":hashlib.sha256((root/"episodes.jsonl").read_bytes()).hexdigest()}}
    (root/"selection_startup_contract.json").write_text(json.dumps(contract,indent=2)+"\n")
PY
'''


def main():
    template = read_pinned({"path": str(TEMPLATE), "sha256": TEMPLATE_SHA})
    parent = read_pinned({"path": str(PARENT), "sha256": PARENT_SHA})
    cases = sorted(parent["cases"], key=lambda c: (c["mode"] != "close", c["episode"]["seed"]))
    if len(cases) != 10 or any(c["episode"]["suite"] != "libero_90" for c in cases):
        raise ValueError("expected the existing ten original microwave development cases")
    for item in [*template["source_snapshot"]["files"], template["source_snapshot"]["archive"],
                 template["launcher"], template["adapter"]]:
        path = Path(item["path"])
        if ref(path)["sha256"] != item["sha256"]:
            raise ValueError("source/launcher changed: " + str(path))
    OUTPUT.mkdir(parents=True, exist_ok=False)
    plans = []
    for index, case in enumerate(cases):
        plan = copy.deepcopy(template)
        key = "public_microwave_dual_temporal_stop"
        case = {**case, "condition": key, "previously_used_for_selection": True,
                "excluded_from_training": True}
        plan.update(cases=[case], producer=ref(Path(__file__).resolve()),
                    producer_dependencies=[ref(TEMPLATE), ref(PARENT), *template["producer_dependencies"]],
                    purpose="repaired original microwave selection10; no confirmation qualification",
                    new_physical_trials=1, training_allowed=False, train_allowed=False)
        plan["conditions"][key]["max_chunks"] = 160
        plan["budget"]["max_chunks"] = 160
        plan["budget"]["note"] = "selection160; public temporal stop after each5-control policy block"
        plan["metrics"]["first_attempt_denominator"] = "one fixed original state/mode; ten total selection attempts"
        plan["pairing"] = "same visited original10 state/setup/prompt; repaired public endpoint; RNG not paired"
        path = OUTPUT / f"case{index}.json"
        path.write_text(json.dumps(plan, indent=2) + "\n")
        plans.append({"index": index, "case": case["name"], "episode": case["episode"],
                      "mode": case["mode"], "manifest": ref(path)})
    wrapper = OUTPUT / "run_selection10.sbatch"
    wrapper.write_text(LAUNCHER)
    index = {"version": "original-microwave-selection10/1", "plans": plans,
             "source": template["source_snapshot"]["path"], "source_snapshot": template["source_snapshot"],
             "launcher": template["launcher"], "wrapper": ref(wrapper),
             "parent_manifest": ref(PARENT), "template_manifest": ref(TEMPLATE),
             "physical_root": str(OUTPUT / "physical"), "confirmation": False,
             "training_allowed": False, "qualification_authorized": False,
             "startup_index": 0, "formal_indices": list(range(1, 10)),
             "startup_is_included_in_selection_denominator": True}
    path = OUTPUT / "index.json"
    path.write_text(json.dumps(index, indent=2) + "\n")
    print(json.dumps({"index": ref(path), "wrapper": ref(wrapper), "plans": 10,
                      "actual_physical_startup_pending": True}))


if __name__ == "__main__":
    main()
