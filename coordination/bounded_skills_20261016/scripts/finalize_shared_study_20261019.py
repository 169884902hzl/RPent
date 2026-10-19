"""Join saved GPU measurements on the login node; never rerun episode physics."""
import argparse
import importlib.util
import json
from collections import Counter
from pathlib import Path


def finalize(root, study_path, launcher):
    """Recount the complete ledgers and independently compare the three traces."""
    study=json.loads(study_path.read_bytes())
    launch=json.loads((root/'launch.json').read_bytes())
    assert launch['source']==study['source']
    assert launch['source_commit']==study['source_commit']
    assert launch['manifest']==study['manifest']
    assert launch['indices']==study['indices'] and launch['domain']=='original'
    assert launcher.digest(study['manifest']['path'])==study['manifest']['sha256']
    serial=Path(launch.get('serial_reference') or root)
    serial_launch=json.loads((serial/'launch.json').read_bytes())
    for key in ['source','source_commit','manifest','indices','domain']:
        assert serial_launch[key]==launch[key]
    expected=Counter(case['name'] for case in study['cases'])

    def level(path):
        report=json.loads((path/'summary.json').read_bytes())
        rows=[json.loads(line) for line in (path/'episodes.jsonl').open()]
        assert len(rows)==len(study['indices'])==report['registered_episodes']
        assert report['source_commit']==study['source_commit'] and not report['startup']
        assert report['worker_errors']==0 and report['physical_episodes']==len(rows)
        assert Counter(row['case']['name'] for row in rows)==expected
        assert all(row['process_exit_code']==0 and row['result']['status']=='physical_result' for row in rows)
        assert sum(row['result']['success'] is True for row in rows)==report['successful_episodes']
        assert report['completed_episodes_per_hour']==report['physical_episodes']*3600/report['wall_s']
        return report

    reports=sorted((level(path) for path in (root/'measurements').glob('N*') if path.name!='N1'),key=lambda row:row['n'])
    assert [row['n'] for row in reports[:3]]==[4,8,12]
    selected=launcher.selected_parallel_n(reports)
    checked=level(root/'consistency'/f'N{selected}')
    assert checked['n']==selected
    baseline=level(serial/'measurements/N1')
    assert baseline['n']==1
    consistency=launcher.compare_three(study,root,selected,serial)
    result=launcher.study_result([baseline,*reports],consistency,study['source_commit'],len(study['indices']),serial)
    result['offline_finalization']={'script':str(Path(__file__).resolve()),
        'script_sha256':launcher.digest(__file__),'launcher_helpers_sha256':launcher.digest(launcher.__file__),
        'study_plan':{'path':str(study_path),'sha256':launcher.digest(study_path)},
        'scope':'saved per-level complete ledgers and full choice traces; GPU job exit/accounting retained separately'}
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True,help='Existing GPU study directory')
    parser.add_argument('--study-plan',type=Path,required=True)
    args=parser.parse_args()
    path=Path(__file__).with_name('shared_gpu_episodes_20261019.py')
    spec=importlib.util.spec_from_file_location('shared_launcher',path)
    launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)
    result=finalize(args.output,args.study_plan,launcher)
    target=args.output/'study_summary.json'
    if target.exists():
        original=json.loads(target.read_bytes())
        for key in ['levels','selected_n','consistency','measured_speedup','adoption_ready']:
            assert original[key]==result[key],key
        target=args.output/'offline_study_summary.json'
    with target.open('x') as stream:
        json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({'output':str(target),'selected_n':result['selected_n'],
        'serial_episodes_per_hour':result['serial_episodes_per_hour'],
        'parallel_episodes_per_hour':result['parallel_episodes_per_hour'],
        'speedup':result['measured_speedup'],'adoption_ready':result['adoption_ready']}),flush=True)
    return 0 if result['adoption_ready'] else 2


if __name__=='__main__':
    raise SystemExit(main())
