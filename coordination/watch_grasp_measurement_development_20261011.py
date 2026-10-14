"""Monitor only this development chain, then release hash-matched formal shards."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT=Path('/public/home/sunyihan/rpent_libero_eval')
OUT=ROOT/'results/harness_v5/grasp_measurement_development_20261011_r4'
LAUNCH=ROOT/'coordination/run_v5_grasp_measurement_development_20261011.sbatch'


def pin(path):
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def available_slots():
    node=subprocess.check_output(['scontrol','show','node','node01','-o'],text=True)
    allocated=next((s.split('=',1)[1] for s in node.split() if s.startswith('AllocTRES=')),'')
    gpu=next((int(s.rsplit('=',1)[1]) for s in allocated.split(',') if s.startswith('gres/gpu=')),0)
    return max(1,4-gpu)


def notify(text):
    print(text,flush=True)
    with Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md').open('a') as f:
        f.write('\n\n### Codex3：抓取测量开发监控\n\n'+text+'\n')


def main():
    registered=json.loads((OUT/'startup_manifest.json').read_text())
    last_state=None
    while True:
        jobs=[]
        for item in registered:
            jobs.append(item['startup_job'])
            path=Path(item['plan']['path']).parent/'formal_measurement_submission.json'
            if path.exists():jobs.append(json.loads(path.read_text())['formal_job'])
        result=subprocess.check_output(['sacct','-X','-n','-j',','.join(jobs),
            '--format=JobID,State,ExitCode','-P'],text=True)
        states={}
        for line in result.splitlines():
            fields=line.split('|')
            if len(fields)>=3:states[fields[0]]=(fields[1].split()[0],fields[2])
        if states!=last_state:
            print(json.dumps({'observed_jobs':states,'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}),flush=True)
            last_state=states
        failures=[(job,state) for job,state in states.items() if state[0] in
                  {'FAILED','TIMEOUT','CANCELLED','NODE_FAIL','OUT_OF_MEMORY','PREEMPTED'}]
        if failures:
            for job,state in failures:
                base=job.split('_')[0]
                part=job.split('_')[1] if '_' in job else '4294967294'
                log=ROOT/'results'/f'slurm-{base}_{part}.log'
                tail=log.read_text(errors='replace')[-6000:] if log.exists() else 'slurm log not yet available'
                error=OUT/f'monitor_failure_{job}.json'
                error.write_text(json.dumps({'job':job,'state':state,'log':str(log),'tail':tail},indent=2)+'\n')
                notify(f'{job} {state}: 已保留失败日志 {error}；未自动重复物理失败。需要定位开发错误后续提。')
            raise SystemExit(1)
        released=0
        for item in registered:
            startup=item['startup_job']
            if states.get(startup)!=('COMPLETED','0:0'):continue
            plan_path=Path(item['plan']['path'])
            record=plan_path.parent/'formal_measurement_submission.json'
            if record.exists():released+=1;continue
            category=plan_path.parent.parent
            contract=category/f'job{startup}/part0/startup_contract.json'
            data=json.loads(contract.read_text())
            if (data['status']!='pass' or data['physical_controls']<=0 or
                    data['plan_sha256']!=item['plan']['sha256'] or
                    data['launcher_sha256']!=pin(LAUNCH)['sha256']):
                raise ValueError('startup contract does not establish this exact physical launcher')
            raw=json.loads(Path(data['episodes']['path']).read_text().splitlines()[0])
            phase=raw.get('private_grasp_phase') or {}
            if not phase.get('samples') or phase.get('trace_version')!='every-executed-skill-control/1-dev':
                raise ValueError('full skill trace missing from completed physical startup')
            plan=json.loads(plan_path.read_text())
            count=len(plan['cases'])-1
            shards=min(8,count)
            env=dict(os.environ,PERTURB_SKILL_PLAN=str(plan_path),
                PERTURB_SKILL_PLAN_SHA=item['plan']['sha256'],PERTURB_SKILL_SOURCE=plan['source_path'],
                PERTURB_SKILL_ADAPTER=plan['adapter_path'],PERTURB_SKILL_OUTPUT=str(category),
                PERTURB_SKILL_STARTUP='0',PERTURB_SKILL_STARTUP_CONTRACT=str(contract),
                PERTURB_SKILL_SHARDS=str(shards))
            job=subprocess.check_output(['sbatch','--parsable','--exclude=node02','--nice=500',
                '--time=02:00:00','--array',f'0-{shards-1}%{available_slots()}',
                '--chdir=/tmp','--export=ALL',str(LAUNCH)],env=env,text=True).strip()
            receipt={'formal_job':job,'startup_job':startup,'startup_contract':pin(contract),
                     'plan':item['plan'],'launcher':pin(LAUNCH),'remaining_cases':count,'shards':shards,
                     'actual_startup_controls':data['physical_controls'],'startup_skill_trace_samples':len(phase['samples']),
                     'resource_rules':{'exclude':'node02','nice':500},'closed_confirmation_reopened':False}
            record.write_text(json.dumps(receipt,indent=2)+'\n')
            notify(f'{category.name}：startup {startup} 实际controls={data["physical_controls"]}，完整轨迹{len(phase["samples"])}帧；正式测量数组{job}已提交，剩余{count}条，exclude=node02/nice=500。')
            released+=1
        if released==len(registered):
            complete=True
            for item in registered:
                formal=json.loads((Path(item['plan']['path']).parent/'formal_measurement_submission.json').read_text())
                parts=[states.get(f'{formal["formal_job"]}_{i}') for i in range(formal['shards'])]
                complete &= all(state==('COMPLETED','0:0') for state in parts)
            if complete:
                notify('五类旧失败/unknown开发测量分片均完成；待按逐状态轨迹与pan16真值unknown核对，不代表确认通过。')
                return
        # Actual submitted startup/formal dependencies remain pending/running.
        time.sleep(60)


if __name__=='__main__':main()
