"""Overlay only evaluated diagnostic changes on the pinned c752 execution tree."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

BASE='c7520ae1219e4b67549b418b9438b271109dd49a'
FILES=['scripts/probe_bounded_hybrid_d2.py','scripts/probe_bounded_hybrid_repair.py',
    'tests/unit_tests/robots/libero/test_bounded_hybrid_diagnostic.py',
    'tests/unit_tests/robots/libero/test_bounded_hybrid_repair.py',
    'tests/unit_tests/robots/libero/fixtures/observe_recovery_receipts_20261022.json']

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--archive',type=Path,required=True);p.add_argument('--factors',action='store_true');p.add_argument('--fulltask',action='store_true');a=p.parse_args()
    root=Path(__file__).resolve().parents[3]
    with tempfile.TemporaryDirectory(prefix='ceiling_source_') as temp:
        env=dict(os.environ,GIT_INDEX_FILE=str(Path(temp)/'index'))
        subprocess.run(['git','read-tree',BASE],cwd=root,env=env,check=True)
        blobs={}
        files = FILES + (['scripts/probe_bounded_option_ceiling.py',
            'coordination/bounded_skills_20261016/scripts/run_schema6_physical_20261020.py',
            'tests/unit_tests/robots/libero/test_bounded_option_ceiling.py'] if a.factors else [])
        if a.fulltask:
            if not a.factors:raise ValueError('fulltask preparation needs the factor launcher')
            files += ['rpent/skill_package/vla.py','tests/unit_tests/robots/libero/test_bounded_vla.py',
                'scripts/probe_bounded_A1_preparation.py','tests/unit_tests/robots/libero/test_bounded_A1_preparation.py',
                'robots/libero/bounded_hybrid_paths.py','tests/unit_tests/robots/libero/test_bounded_hybrid_paths.py',
                'robots/libero/bounded_async.py',
                'coordination/bounded_skills_20261016/scripts/original_model_closedloop_20261021.py',
                'tests/unit_tests/robots/libero/test_bounded_model_probe.py']
        for f in files:
            blob=subprocess.check_output(['git','rev-parse','HEAD:'+f],cwd=root,text=True).strip()
            subprocess.run(['git','update-index','--add','--cacheinfo','100644,'+blob+','+f],cwd=root,env=env,check=True);blobs[f]=blob
        if a.fulltask:
            f='robots/libero/bounded_skills.py'
            raw=subprocess.check_output(['git','show',BASE+':'+f],cwd=root,text=True)
            needle='        result = run_fallback(prompt=prompt, prepare=prepare, predict=predict, step=step,\n'
            replacement="        from rpent.skill_package.vla import whole_instruction_budget\n\n        budget = whole_instruction_budget(self.vla_budget) if mode == 'task' else self.vla_budget\n"+needle
            assert raw.count(needle)==1
            raw=raw.replace(needle,replacement).replace('            handoff=handoff, budget=self.vla_budget)','            handoff=handoff, budget=budget)')
            blob=subprocess.check_output(['git','hash-object','-w','--stdin'],input=raw,cwd=root,text=True).strip()
            subprocess.run(['git','update-index','--cacheinfo','100644,'+blob+','+f],cwd=root,env=env,check=True);blobs[f]=blob
        tree=subprocess.check_output(['git','write-tree'],cwd=root,env=env,text=True).strip()
    unchanged=['robots/libero/bounded_screen.py','robots/libero/bounded_oracle.py','robots/libero/bounded_chunk.py','robots/libero/bounded_motion.py']
    if not a.fulltask:unchanged+=['robots/libero/bounded_skills.py','rpent/skill_package/vla.py']
    for f in unchanged:
        assert subprocess.check_output(['git','rev-parse',BASE+':'+f],cwd=root)==subprocess.check_output(['git','rev-parse',tree+':'+f],cwd=root)
    a.output.mkdir(parents=True,exist_ok=False)
    with a.archive.open('xb') as f: subprocess.run(['git','archive','--format=tar.gz',tree],cwd=root,stdout=f,check=True)
    subprocess.run(['tar','-xzf',str(a.archive),'-C',str(a.output)],check=True)
    evidence={'base':BASE,'commit':tree,'overlay_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        'files':blobs,'archive_sha256':hashlib.sha256(a.archive.read_bytes()).hexdigest(),'execution_stack_unchanged':not a.fulltask,'runtime_change':'whole_instruction_default_budget; separate_native_completion; HTTP_evaluation_logging' if a.fulltask else None,'dirty_tree_included':False,'training':False}
    (a.output/'SOURCE_REVISION.json').write_text(json.dumps(evidence,indent=2)+'\n')
    Path(str(a.archive)+'.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(evidence))

if __name__=='__main__':main()
