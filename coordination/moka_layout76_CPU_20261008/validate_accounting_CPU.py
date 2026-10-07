"""Run the generated launcher's formal exit guard on a real binding-missing row."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--preparation",type=Path,required=True)
    parser.add_argument("--ledger",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    ledger=args.ledger.read_bytes()
    original=next(json.loads(line) for line in ledger.decode().splitlines()
                  if json.loads(line)["case"]["name"]=="moka_layout_580104")
    plan=json.loads((args.preparation/"moka_layout76.json").read_text())
    launcher=args.preparation/"run_moka_layout76.sbatch"
    assert hashlib.sha256(launcher.read_bytes()).hexdigest()==plan["launcher_identity"]["sha256"]
    text=launcher.read_text()
    guard=text.rsplit("<<'PY'\n",1)[1].split("\nPY",1)[0]
    dependency=args.preparation/"check_v5_moka_formal_accounting_20261008.py"
    cases=[]
    def register(name,mutator,expected_nonzero=False,runner_rc=0):
        row=copy.deepcopy(original);mutator(row);cases.append((name,row,expected_nonzero,runner_rc))
    register("real_completed_binding_missing_unknown",lambda r:None)
    register("physical_completed",lambda r:r.update(server_chunk_execution={"requested_controls":5}))
    register("startup_error",lambda r:r["result"].update(status="startup_error"),True)
    register("infrastructure_failure",lambda r:r.update(case_had_infrastructure_failure=True),True)
    register("execution_error",lambda r:r["first_receipt"].update(verification="execution_error"),True)
    register("unaccounted_zero_controls",lambda r:r["first_receipt"].pop("executed"),True)
    register("runner_nonzero",lambda r:None,True,1)
    records=[]
    for name,row,error,rc in cases:
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            (root/"episodes.jsonl").write_text(json.dumps(row)+"\n")
            (root/"startup_dependency_audit.json").write_text(json.dumps({"path":str(dependency),
                "sha256":hashlib.sha256(dependency.read_bytes()).hexdigest()})+"\n")
            result=subprocess.run(["python3","-c",guard,str(root),str(rc)],
                env={"PATH":"/usr/bin:/bin","PYTHONPATH":str(args.preparation)},capture_output=True,text=True)
            passed=(result.returncode!=0)==error
            contract=json.loads((root/"contract.json").read_text()) if (root/"contract.json").is_file() else None
            if name=="real_completed_binding_missing_unknown":
                passed=passed and contract["legitimate_no_execution_cases"][0]["outcome"]=="unknown"
            records.append({"case":name,"passed":passed,"exit_code":result.returncode,
                            "contract":contract,"stderr":result.stderr})
    output={"schema":"moka76-formal-accounting-CPU/1","source_ledger":{"path":str(args.ledger),
             "sha256":hashlib.sha256(ledger).hexdigest()},"source_case":"moka_layout_580104",
             "launcher":{"path":str(launcher),"sha256":hashlib.sha256(launcher.read_bytes()).hexdigest()},
             "physical_execution":False,"cases":records,"passed":all(r["passed"] for r in records),
             "startup_positive_controls_gate_unchanged":True}
    args.output.write_text(json.dumps(output,indent=2)+"\n")
    print(json.dumps({"passed":output["passed"],"tests":len(records),
                      "exit_codes":{r["case"]:r["exit_code"] for r in records}}))
    if not output["passed"]:raise SystemExit(1)


if __name__=="__main__":
    main()
