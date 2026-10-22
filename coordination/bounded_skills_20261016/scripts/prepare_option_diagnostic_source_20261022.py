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
    'tests/unit_tests/robots/libero/fixtures/observe_recovery_receipts_20261022.json',
    'tests/unit_tests/robots/libero/fixtures/vla_retry_before_loop_20261023.json']


def staged_adapter(raw):
    """Add the reviewed compound option to the qualified executor, not dirty HEAD."""
    def replace(before,after):
        nonlocal raw
        assert raw.count(before)==1,before
        raw=raw.replace(before,after)
    replace("            for preparation in ('in_place','initial_pose'):\n",
        "            preparations = ('in_place','initial_pose') + (('measured_anchor',)\n"
        "                if parameters.get('anchor_id') and parameters['mode'] not in {'task','instruction'} else ())\n"
        "            for preparation in preparations:\n")
    replace("                if key in getattr(self,'_vla_failed_options',set()):\n",
        "                if preparation != 'measured_anchor' and key in getattr(self,'_vla_failed_options',set()):\n")
    replace('            consequence["screen_scope"] = "unmeasured"\n',
        '            consequence["screen_scope"] = "unmeasured"\n'
        "            if parameters.get('preparation') == 'measured_anchor':\n"
        "                from robots.libero.bounded_vla_staged import estimate_steps\n"
        "                consequence['expected_steps'] += estimate_steps(self, parameters)\n"
        "                history = {'success_rate': None, 'n': 0, 'expected_steps': None, 'source_manifest_sha256': None}\n")
    replace('        def prepare():\n',
        '        def prepare():\n'
        '            nonlocal source, target\n'
        "            if parameters.get('preparation') == 'measured_anchor':\n"
        "                from robots.libero.bounded_vla_staged import prepare as prepare_measured\n"
        '                prepared = prepare_measured(self, parameters)\n'
        "                source = self.scene.entities.get(parameters['anchor_id'], source)\n"
        "                target = self.scene.entities.get(parameters.get('target_id'), target)\n"
        '                return prepared\n')
    replace("            first_measurement = result['post_handoff_measurement']\n",
        "            first_measurement = result['post_handoff_measurement']\n"
        "            native_staged_completion = False\n"
        "            if parameters.get('preparation') == 'measured_anchor':\n"
        "                result['raw_policy_outcome'] = {k: result[k] for k in ('outcome', 'stop_reason', 'blocks_used')}\n"
        "                if mode in {'on','in'} and result['preparation']['success'] and not first_measurement['completed']:\n"
        "                    from robots.libero.bounded_vla_staged import transport\n"
        "                    result['scripted_transport'] = transport(self, parameters)\n"
        "                    result['timing_s']['scripted_transport'] = result['scripted_transport']['wall_s']\n"
        "                    native_staged_completion = bool(self.p.env.terminated)\n"
        "                    result['post_handoff_measurement'] = observe(full=True)\n"
        "                    first_measurement = result['post_handoff_measurement']\n"
        "                result['native_completion_after_scripted_transport'] = native_staged_completion\n")
    replace('            final_completed = result["post_handoff_measurement"]["completed"]\n',
        '            final_completed = result["post_handoff_measurement"]["completed"] or native_staged_completion\n')
    replace("                result.update(outcome='success',stop_reason='measured_success_after_handoff')\n",
        "                result.update(outcome='success',stop_reason=('native_success_after_scripted_transport'\n"
        "                    if native_staged_completion else 'measured_success_after_handoff'))\n")
    replace('        result["template"] = {"version": PI05_PROMPT_VERSION, "mode": mode, "prompt": prompt}\n',
        "        if (parameters.get('preparation') == 'measured_anchor' and not result['preparation']['success']\n"
        "                and result['steps_used'] == 0):\n"
        "            result['phase'] = 'planning_unreachable'\n"
        '        result["template"] = {"version": PI05_PROMPT_VERSION, "mode": mode, "prompt": prompt}\n')
    replace('                phase = None if outcome == "success" else "contact_failure"\n',
        '                phase = None if outcome == "success" else detail.get("phase", "contact_failure")\n')
    compile(raw,'qualified_measured_vla_adapter','exec')
    return raw

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--archive',type=Path,required=True);p.add_argument('--factors',action='store_true');p.add_argument('--fulltask',action='store_true');p.add_argument('--staged',action='store_true');a=p.parse_args()
    if a.staged and not a.fulltask:p.error('--staged requires --fulltask')
    root=Path(__file__).resolve().parents[3]
    with tempfile.TemporaryDirectory(prefix='ceiling_source_') as temp:
        env=dict(os.environ,GIT_INDEX_FILE=str(Path(temp)/'index'))
        subprocess.run(['git','read-tree',BASE],cwd=root,env=env,check=True)
        blobs={}
        files = FILES + (['scripts/probe_bounded_option_ceiling.py',
            'coordination/bounded_skills_20261016/scripts/run_schema6_physical_20261020.py',
            'coordination/bounded_skills_20261016/scripts/run_schema6_stage_20261020.sbatch',
            'tests/unit_tests/robots/libero/test_bounded_option_ceiling.py'] if a.factors else [])
        if a.fulltask:
            if not a.factors:raise ValueError('fulltask preparation needs the factor launcher')
            files += ['rpent/skill_package/vla.py','tests/unit_tests/robots/libero/test_bounded_vla.py',
                'scripts/probe_bounded_A1_preparation.py','tests/unit_tests/robots/libero/test_bounded_A1_preparation.py',
                'robots/libero/bounded_hybrid_paths.py','tests/unit_tests/robots/libero/test_bounded_hybrid_paths.py',
                'robots/libero/bounded_async.py',
                'coordination/bounded_skills_20261016/scripts/original_model_closedloop_20261021.py',
                'tests/unit_tests/robots/libero/test_bounded_model_probe.py']
        if a.staged:
            files += ['robots/libero/bounded_vla_staged.py','rpent/skill_package/schema7.json',
                'tests/unit_tests/robots/libero/test_bounded_vla_staged.py',
                'robots/libero/bounded_offline_labels.py',
                'tests/unit_tests/robots/libero/test_bounded_vla_options.py']
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
            if a.staged:raw=staged_adapter(raw)
            blob=subprocess.check_output(['git','hash-object','-w','--stdin'],input=raw,cwd=root,text=True).strip()
            subprocess.run(['git','update-index','--cacheinfo','100644,'+blob+','+f],cwd=root,env=env,check=True);blobs[f]=blob
        if a.staged:
            for f,raw in [('rpent/skill_package/schema.json',subprocess.check_output(
                    ['git','show','HEAD:rpent/skill_package/schema7.json'],cwd=root,text=True)),
                    ('rpent/skill_package/__init__.py',subprocess.check_output(
                    ['git','show',BASE+':rpent/skill_package/__init__.py'],cwd=root,text=True).replace('bounded-skills/6','bounded-skills/7'))]:
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
        'files':blobs,'archive_sha256':hashlib.sha256(a.archive.read_bytes()).hexdigest(),'execution_stack_unchanged':not a.fulltask,'runtime_change':('measured_anchor_vla/1; schema7' if a.staged else 'whole_instruction_default_budget; separate_native_completion; HTTP_evaluation_logging' if a.fulltask else None),'dirty_tree_included':False,'training':False}
    (a.output/'SOURCE_REVISION.json').write_text(json.dumps(evidence,indent=2)+'\n')
    Path(str(a.archive)+'.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(evidence))

if __name__=='__main__':main()
