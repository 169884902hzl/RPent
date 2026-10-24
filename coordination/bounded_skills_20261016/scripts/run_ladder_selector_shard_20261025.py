# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Run an existing ladder shard with the registered inherited-GPU selector."""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import urllib.request


def with_endpoint(plan, endpoint, health):
    expected = plan['model_service']['adapter_sha256']
    if health.get('status') != 'ok' or health.get('adapter_sha256') != expected:
        raise ValueError('sidecar health or adapter differs from registered model A')
    if not endpoint.startswith('http://127.0.0.1:') or not endpoint.endswith('/v1/bounded-choice'):
        raise ValueError('sidecar must use its job-local loopback endpoint')
    result = copy.deepcopy(plan)
    result['model_service'].update(endpoint=endpoint,
        health_url=endpoint.removesuffix('/v1/bounded-choice')+'/health',
        service_job=os.environ.get('SLURM_JOB_ID'), deployment='inherited_GPU_sidecar',
        reference_service_job=plan['model_service']['service_job'])
    result['model_line']='original A, inherited-GPU selector sidecar; same weights and readout'
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--shards',type=Path,required=True)
    p.add_argument('--index',type=int,required=True)
    p.add_argument('--selector-url',default=os.environ.get('BOUNDED_SELECTOR_ENDPOINT'))
    p.add_argument('--prepare-only',action='store_true')
    p.add_argument('--parallel',type=int)
    p.add_argument('--pilot-ack',type=Path)
    p.add_argument('--sidecar-package',type=Path)
    a=p.parse_args();shard=json.loads(a.shards.read_bytes())[a.index]
    manifest=Path(shard['manifest']);plan=json.loads(manifest.read_bytes())
    if not a.selector_url:raise ValueError('sidecar endpoint is required')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(a.selector_url.removesuffix('/v1/bounded-choice')+'/health',timeout=20) as response:
        health=json.load(response)
    plan=with_endpoint(plan,a.selector_url,health)
    if a.parallel is not None:
        if a.parallel<1:raise ValueError('parallel must be positive')
        plan['parallel']=a.parallel
    output=Path(shard['output']);output.mkdir(parents=True,exist_ok=True)
    active=output/'sidecar_manifest.json'
    with active.open('x') as f:json.dump(plan,f,indent=2)
    record={'source_manifest':str(manifest),'source_manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),
        'runtime_manifest':str(active),'runtime_manifest_sha256':hashlib.sha256(active.read_bytes()).hexdigest(),
        'endpoint':a.selector_url,'adapter_sha256':health['adapter_sha256'],
        'changed_fields':['model_service.endpoint','model_service.health_url','model_service.service_job',
            'model_service.deployment','model_service.reference_service_job','model_line']}
    if a.parallel is not None:record['changed_fields'].append('parallel')
    record['parallel_workers']=plan.get('parallel',8)
    (output/'sidecar_binding.json').write_text(json.dumps(record,indent=2)+'\n')
    if a.prepare_only:return
    subprocess.run([sys.executable,str(a.source/'coordination/bounded_skills_20261016/scripts/run_task_ladder_20261025.py'),
        '--source',str(a.source),'--manifest',str(active),'--output',str(output)],check=True)
    root=Path('/public/home/sunyihan/rpent_libero_eval')
    subprocess.run([sys.executable,str(root/'notify_task_board_level_20261025.py'),
        '--shards',str(a.shards),'--index',str(a.index)],check=True)
    if a.pilot_ack:
        if a.sidecar_package is None:raise ValueError('pilot requires its delivered parity package')
        subprocess.run([sys.executable,str(root/'check_ladder_sidecar_shard_20261025.py'),
            '--source',str(a.source),'--shards',str(a.shards),'--index',str(a.index),
            '--ack',str(a.pilot_ack),'--package-root',str(a.sidecar_package),
            '--selector-url',a.selector_url],check=True)


if __name__=='__main__':main()
