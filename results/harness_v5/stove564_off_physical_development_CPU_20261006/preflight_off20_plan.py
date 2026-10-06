"""CPU-only explicit identity check for the fixed original off20 design."""

import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--expected-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    data=args.manifest.read_bytes()
    if not args.manifest.is_absolute() or hashlib.sha256(data).hexdigest()!=args.expected_sha256:
        raise ValueError('registered off20 manifest changed')
    plan=json.loads(data);checked=[]
    def verify(ref):
        path=Path(ref['path']);data=path.read_bytes()
        if not path.is_absolute() or hashlib.sha256(data).hexdigest()!=ref['sha256']:
            raise ValueError('registered original source or metadata changed')
        checked.append(ref)
    verify(plan['original_sampling_manifest']);verify(plan['base_config'])
    original=json.loads(Path(plan['original_sampling_manifest']['path']).read_text())
    for name,sha in plan['source_sha256'].items():verify({'path':str(Path(plan['source_root'])/name),'sha256':sha})
    assert len(plan['cells'])==20 and len(plan['methods'])==4 and plan['original_case_count']==5
    assert all(c['original_case']==original['cases'][i//4] for i,c in enumerate(plan['cells']))
    assert all(c['original_case']['episode']['suite']=='libero_goal' and c['original_case']['episode']['task']==7 for c in plan['cells'])
    assert all(c['original_case']['episode']['seed'] in range(5) for c in plan['cells'])
    assert plan['fixed_on_chunks']==160 and plan['fixed_off_chunks']==160 and plan['actions_per_chunk']==5
    assert not plan['private_scoring']['controller_access'] and not plan['private_scoring']['affects_actions']
    assert not plan['private_scoring']['affects_stop'] and not plan['private_scoring']['affects_binding']
    assert not plan['implementation']['GPU_submission_ready']
    report={'passed':True,'manifest':{'path':str(args.manifest),'sha256':args.expected_sha256},
            'checked_files':checked,'cells':20,'paired_original_states':5,'cwd':str(Path.cwd()),
            'schema_and_source_identity_only':True,'GPU_submission_ready':False,
            'server_or_simulator_started':False,'private_labels_opened':False,'qualification_authorized':False}
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':True,'cells':20,'GPU_submission_ready':False,'server_or_simulator_started':False}))


if __name__=='__main__':main()
