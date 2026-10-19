"""Pin the six handoff replays and three paired stopping-rule comparisons."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path


ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
BASE = ROOT / 'coordination/bounded_skills_20261016'
CALIBRATION = ROOT/'results/harness_v5/gripper513_original_opening_calibration_20261005/runtime_calibration.json'


def read(path):
    return json.loads(path.read_bytes())


def ref(path):
    return {'path':str(path.resolve()), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--archive-sha256', required=True)
    parser.add_argument('--submit-startup', action='store_true')
    parser.add_argument('--schema-v4', action='store_true')
    parser.add_argument('--grasp-calibration', type=Path, default=CALIBRATION)
    args = parser.parse_args()
    assert ref(args.archive)['sha256'] == args.archive_sha256
    source = ROOT / ('source_bounded_hybrid_handoff_20261019_'+args.commit[:8])
    source.mkdir()
    with tarfile.open(args.archive) as archive:
        archive.extractall(source)
    directory = ROOT / 'results/bounded_skills/hybrid_repair_20261019' / args.commit[:8] / 'preparation'
    directory.mkdir(parents=True)
    registry = BASE / 'preparation/D2_handoff_six_20261019.json'
    six = read(registry)['rows']
    calibration = ref(args.grasp_calibration)
    cases = []
    baseline = {'blocks':24,'no_progress_blocks':3,'controls_per_check':1,'minimum_progress_m':.005,'max_controls':None}
    def case(row, variant, budget):
        path = Path(row['raw_summary'])
        old = read(path)
        original = read(path.parents[3]/'assignment.json')['case']
        return {**original, 'name':original['name']+'_'+variant+'_r'+str(row['seed']),
            'grasp_measurement_calibration': calibration,
            'diagnostic':{'kind':'replay', 'domain':'d2', 'variant':variant,
                'old_summary':ref(path), 'branchpoint':ref(Path(row['branchpoint'])), 'budget':budget,
                'migrate_v3_header_to_v4':args.schema_v4}}
    cases.extend(case(row, 'handoff', baseline) for row in six)
    for row in six:
        if read(Path(row['raw_summary']))['success'] is not False:
            continue
        for controls in (120, 220):
            cases.append(case(row, 'progress_off_'+str(controls),
                {**baseline,'no_progress_blocks':None,'max_controls':controls,'blocks':(controls+4)//5}))
    assert len(cases) == 12 and len({x['name'] for x in cases}) == 12
    manifest = directory/'manifest.json'
    write(manifest, {'evaluation':'hybrid_repair', 'source_commit':args.commit,
        'cases':cases,'training':False,'confirmation':False,'registered_six':ref(registry),
        'scope':'six handoff replays + three failed seeds x two stopping settings; no D2 whole-case score',
        'legacy_observation_limit':'old checkpoints omit observable phase/buffers; the new complete-state implementation records canonical fresh reconstruction rather than claiming exact historical policy-input replay',
        'stop_comparison':'disable no-progress; retain measured-success, region and native stop conditions; same original sampling seed',
        'openpi_reference':{'url':'https://github.com/Physical-Intelligence/openpi/blob/main/examples/libero/main.py',
            'access_date_pacific':'2026-10-19','replan_steps':5,'stabilization_steps':10,
            'max_controls':{'libero_spatial':220,'libero_object':280,'libero_goal':300,'libero_10':520,'libero_90':400}}})
    batch = {'domain':'d2','source':str(source),'source_commit':args.commit,'manifest':ref(manifest)}
    full = {'selected_n':8, 'batches':[{**batch,'indices':list(range(6))},
        {**batch,'indices':list(range(6,12))}],'training':False,'confirmation':False}
    startup = {**full, 'batches':[{**batch,'indices':[0,6,7]}]}
    write(directory/'batch_plan.json', full)
    write(directory/'startup_plan.json', startup)
    script = source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py'
    launcher = ROOT / ('launcher_shared_20261019_'+ref(script)['sha256'][:12])
    launcher.mkdir(exist_ok=True)
    for name in (script.name,'run_shared_batch_20261019.sbatch'):
        target = launcher/name
        if target.exists():
            assert target.read_bytes() == (script.parent/name).read_bytes()
        else:
            shutil.copy2(script.parent/name,target)
    env = dict(os.environ,CUDA_VISIBLE_DEVICES='',LIBERO_CONFIG_PATH=str(ROOT/'runtime_config'),
        OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    preflights = []
    for name, plan in (('batch',full),('startup',startup)):
        for index in range(len(plan['batches'])):
            command = [str(ROOT/'.venv/bin/python'),str(launcher/script.name),
                '--batch-plan',str(directory/(name+'_plan.json')),'--batch-index',str(index),'--preflight']
            checked = subprocess.run(command,cwd=ROOT,env=env,text=True,capture_output=True)
            log = directory/f'{name}_{index}_preflight.log'
            log.write_text(checked.stdout+checked.stderr)
            checked.check_returncode()
            preflights.append({'command':command,'exit_code':0,'log':str(log)})
    report = {'source_commit':args.commit,'source':str(source),'archive':ref(args.archive),
        'manifest':ref(manifest),'launcher':ref(launcher/script.name),'preflights':preflights,
        'preparation':str(directory),'training':False,'confirmation':False,'production_submitted':False}
    write(directory/'preparation.json', report)
    if args.submit_startup:
        submit_env = dict(os.environ,BATCH_PLAN=str(directory/'startup_plan.json'),
            LAUNCHER=str(launcher/script.name),STARTUP='1',RESULTS_ROOT=str(directory.parent))
        command = ['sbatch','--parsable','--nodelist=node02','--nice=500','--array=0%1',
            '--export=ALL',str(launcher/'run_shared_batch_20261019.sbatch')]
        job = subprocess.check_output(command,cwd=ROOT,env=submit_env,text=True).strip().split(';')[0]
        report = {**report,'job':job,'command':command,'startup':True}
        write(directory/'startup_submission.json',report)
    print(json.dumps(report),flush=True)


if __name__ == '__main__':
    main()
