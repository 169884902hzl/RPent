"""Reclaim only explicitly registered C3 jobs when C2 needs a GPU slot."""
import argparse
import datetime
import json
import re
import subprocess
import time
from pathlib import Path

ACTIVE={'RUNNING','CONFIGURING','COMPLETING'}


def gpu_count(row):
    match=re.search(r'gpu(?::[^,:]+)?:(\d+)',row[4])
    return int(match.group(1)) if match else 0


def reclaim_jobs(rows, registered):
    c2=[r for r in rows if r[1].startswith('rd-c2-') and gpu_count(r)
        and r[2] in {'PENDING','RUNNING','CONFIGURING'} and r[5] not in {'JobHeldUser','JobHeldAdmin'}]
    owned=[r for r in rows if r[0] in registered]
    for row in owned:
        if not row[1].startswith('rd-c3-s6-v7-') or row[5]=='JobHeldUser':
            raise ValueError('registered job is not a reclaimable v7 development job')
    running=[r for r in owned if r[2] in ACTIVE and r[3]=='node02']
    c3_running=[r for r in rows if r[1].startswith('rd-c3-') and r[2] in ACTIVE
        and r[3]=='node02' and gpu_count(r)]
    occupied=sum(gpu_count(r) for r in rows if r[2] in ACTIVE and r[3]=='node02')
    waiting=any(r[2]=='PENDING' for r in c2)
    need_slot=bool(c2) and (len(c3_running)>3 or waiting and occupied>=4)
    if not need_slot or not running:return [],c2,occupied
    # Cancel eligible queued jobs first so none can take the returned slot.
    # All completed cases remain on disk. The parent resumes these exact
    # manifests after C2 starts, rather than releasing historical held jobs.
    pending=[r[0] for r in owned if r[2]=='PENDING']
    selected=max(running,key=lambda r:int(r[0]))[0]
    return [*pending,selected],c2,occupied


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host',default='gpu5880-ts')
    p.add_argument('--jobs',nargs='+',required=True)
    p.add_argument('--ledger',type=Path,required=True)
    a=p.parse_args();registered=set(a.jobs)
    assert all(j.isdigit() for j in registered)
    with a.ledger.open('x',buffering=1) as log:
        while True:
            at=datetime.datetime.now().astimezone().isoformat()
            try:
                raw=subprocess.check_output(['ssh','-o','ConnectTimeout=15',a.host,
                    'squeue -h -o "%i|%j|%T|%N|%b|%r"'],text=True,timeout=45)
                rows=[line.split('|',5) for line in raw.splitlines()]
                cancel,c2,occupied=reclaim_jobs(rows,registered)
                event={'at':at,'registered_jobs':sorted(registered),'c2':[r[0] for r in c2],
                    'node02_allocated_gpus':occupied,'cancel':cancel}
                if cancel:
                    subprocess.run(['ssh',a.host,'scancel '+' '.join(cancel)],check=True,timeout=45)
                    event['action']='cancel_registered_waiting_jobs_and_one_borrowed_running_fragment'
                live=[r[0] for r in rows if r[0] in registered]
                event['live']=live
                log.write(json.dumps(event)+'\n');print(json.dumps(event),flush=True)
                if not live:return 0
            except (OSError,subprocess.SubprocessError) as exc:
                log.write(json.dumps({'at':at,'query_error':str(exc)})+'\n')
            time.sleep(30)


if __name__=='__main__':raise SystemExit(main())
