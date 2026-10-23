"""Verify every continuation starts at its exact retained first-pi endpoint."""
import hashlib
import json
import os
from pathlib import Path
import pickle
import sys

root=Path('/public/home/sunyihan/rpent_libero_eval')
source=root/'source_pi_first_origin_f6ce1d46_20261023'
run=root/'results/bounded_skills/next_b_pi_first_20261023'
os.environ.update(LIBERO_TYPE='pro',LIBERO_CONFIG_PATH=str(root/'runtime_config'),
    MUJOCO_GL='egl',PYOPENGL_PLATFORM='egl',CUDA_VISIBLE_DEVICES='',
    HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
sys.path.insert(0,str(source));os.chdir(source)
import robots.libero.env_server
from robots.libero.bounded_hybrid_diagnostic import snapshot_digest

def ref(path):return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

parent=json.loads((run/'preparation/pi_first_oracle_parent_origin.json').read_text())
rows=[]
for shard in range(4):
    plan=json.loads((run/f'preparation/pi_first_oracle_origin_{shard}.json').read_text())
    for i,job in enumerate(plan['jobs']):
        name=job['case']['name'];print(json.dumps({'checking':name}),flush=True)
        original=parent['initial_state_by_case'][name];before_path=Path(original['path'])
        assert ref(before_path)==original
        path=run/f'pi_first_oracle_origin_{shard}'/f'case{i:03d}'/'episode/private_initial.pkl'
        before=pickle.loads(before_path.read_bytes())['physics']
        after=pickle.loads(path.read_bytes())['physics']
        first=snapshot_digest(before);actual=snapshot_digest(after)
        row={'case':name,'first_end':original,'actual_initial':ref(path),
            'first_end_physics_sha256':first,'actual_initial_physics_sha256':actual,'equal':first==actual}
        rows.append(row);print(json.dumps({'checked':name,'equal':row['equal']}),flush=True)
assert len(rows)==24 and all(r['equal'] for r in rows)
output=run/'CPU_first_end_to_oracle_initial_physics_r2.json'
with output.open('x') as f:json.dump({'n':24,'matches':24,'rows':rows,'physical_steps':0,'training':False},f,indent=2)
print(json.dumps(ref(output)),flush=True)
