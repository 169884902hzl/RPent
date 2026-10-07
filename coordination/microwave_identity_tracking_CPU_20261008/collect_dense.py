"""Read one explicit owned dense ledger; retain private labels separately."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess


REMOTE = r'''
from pathlib import Path
import hashlib,json,subprocess
root=Path('/public/home/sunyihan/rpent_libero_eval')
plan_path=root/'results/harness_v5/microwave_identity_tracking_CPU_20261008/r1/close_dense40.json'
output=root/'results/harness_v5/microwave_dense_public_original_20261008/close40'
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def lines(p):
 if not p.is_file():return []
 raw=p.read_text();rows=raw.splitlines()
 if raw and not raw.endswith('\n'):rows=rows[:-1]
 return [json.loads(line) for line in rows if line.strip()]
if ref(plan_path)['sha256']!='f8eea2ed143bc3e3476a1bffe57f9a15fc261350de0ca15cced26e11748cbf0e':raise ValueError('registered dense plan changed')
public=output/'dense_public/public_captures.jsonl';private=output/'dense_public/private_labels.jsonl'
ledger=output/'episodes.jsonl';contract=output/'physical_startup_contract.json'
accounting=subprocess.run(['sacct','-j','__JOB__','--format=JobID,State,ExitCode,Elapsed,NodeList','-P'],capture_output=True,text=True,check=True).stdout
rows,labels,episodes=lines(public),lines(private),lines(ledger)
if len(episodes)>1:raise ValueError('only one original development episode is registered')
inputs=[ref(plan_path)]+[ref(p) for p in (public,private,ledger,contract) if p.is_file()]
result={'job':__JOB__,'sacct':accounting,'inputs':inputs,'public_records':rows,'private_labels':labels,
 'episodes':episodes,'physical_startup_contract':json.loads(contract.read_text()) if contract.is_file() else None,
 'train_allowed':False,'qualification':False,'directory_scan_used':False}
print(json.dumps(result))
'''


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.job <= 0 or args.output.exists():
        raise ValueError("positive job and fresh output required")
    run = subprocess.run(["ssh", "gpu5880-ts", "python3", "-"],
        input=REMOTE.replace("__JOB__", str(args.job)), text=True, capture_output=True, check=True)
    result = json.loads(run.stdout)
    args.output.write_bytes(gzip.compress((json.dumps(result, indent=2) + "\n").encode(), mtime=0))
    public_output = args.output.with_name(args.output.name.removesuffix(".json.gz") + ".public.json")
    if public_output.exists():
        raise FileExistsError(public_output)
    public_payload = {"job": args.job, "public_records": result["public_records"],
        "runtime_public_records": [item for episode in result["episodes"]
            for item in ((episode.get("first_attempt") or {}).get("verification_measurements") or {}).get("microwave_temporal", [])],
        "private_labels_included": False, "train_allowed": False, "qualification": False}
    public_output.write_text(json.dumps(public_payload, indent=2) + "\n")
    print(json.dumps({"path": str(args.output), "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "public_output": str(public_output),
        "job": args.job, "public_frames": len(result["public_records"]),
        "private_labels": len(result["private_labels"]), "completed_episodes": len(result["episodes"]),
        "physical_startup_contract": result["physical_startup_contract"], "sacct": result["sacct"]}))
