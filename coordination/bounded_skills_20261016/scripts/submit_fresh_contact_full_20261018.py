"""Launch current-source fixture episodes after verified physical startup."""
import hashlib
import json
import subprocess
from pathlib import Path

root=Path("/public/home/sunyihan/rpent_libero_eval")
base=root/"coordination/bounded_skills_20261016"
receipt=json.loads((base/"reports/fresh_contact_submission_20261018.json").read_text())
source=Path(receipt["snapshot"])
startup=root/"results/bounded_skills/feasibility_20261017/job8160_100"
physical=next(startup.glob("*/first_physical_request.json"))
request=json.loads(physical.read_text())
assert request["sim_steps"]>0,request
accounting=subprocess.check_output(["sacct","-X","-n","-j","8160_100","--format=State,ExitCode","-P"],text=True).strip()
assert accounting=="COMPLETED|0:0",accounting
queue=subprocess.check_output(["squeue","-r","-h","-u","sunyihan","-o","%i|%j|%T|%N"],text=True)
ours=[r.split("|") for r in queue.splitlines() if r.split("|")[1].startswith("rd-bounded-")]
assert {r[0].split("_")[0] for r in ours} <= {"8117","8151","8158","8159","8160"},ours
assert sum(r[2]=="RUNNING" for r in ours)<=3
replaced=[r for r in ours if r[0]=="8151_140"]
assert len(replaced)==1 and replaced[0][2]=="PENDING",replaced
subprocess.run(["scancel","8151_140"],check=True)
export="ALL,SOURCE="+str(source)+",SOURCE_COMMIT="+receipt["source_commit"]+",MANIFEST="+receipt["manifest"]["path"]+",STARTUP=0"
def submit(array,dependency):
 args=["sbatch","--parsable","--nodelist=node02","--nice=500","--array="+array,"--dependency=afterany:"+dependency,
       "--export="+export,str(source/"scripts/run_bounded_21f0744_20261017.sbatch")]
 return {"job":subprocess.check_output(args,text=True).strip(),"arguments":args}
full=submit("100%1","8160")
representatives=submit("80,120,180,200%1",full["job"])
microwave=submit("140%1","8117")
report={"source_commit":receipt["source_commit"],"snapshot":str(source),"manifest":receipt["manifest"],
 "startup_accounting":accounting,"startup_physical_request":{"path":str(physical),"sha256":hashlib.sha256(physical.read_bytes()).hexdigest(),**request},
 "paired_drawer_open":full,"fixture_representatives":representatives,"microwave_open":microwave,
 "replaced_pending":replaced,"replacement_reason":"replace unstarted old-source startup with current verified-source full original microwave episode",
 "aggregate_cap":3,"scope":"original-scene oracle development,pi05 disabled;not training/confirmation;running jobs preserved"}
(base/"reports/fresh_contact_full_submission_20261018.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps({k:v for k,v in report.items() if k!="replaced_pending"},indent=2))
