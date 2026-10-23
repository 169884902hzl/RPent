from pathlib import Path
import ast,hashlib,json,subprocess
root=Path('/public/home/sunyihan/rpent_libero_eval');run=root/'results/bounded_skills/success_feedback_20261024'
assert not (run/'preparation/default63_r2/manifest.json').exists(), 'resume plan is already registered'
old_plan=run/'preparation/default63/manifest.json';plan=json.loads(old_plan.read_bytes());source=Path(plan['source'])
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def checked(r):
 p=Path(r['path']);assert ref(p)=={k:r[k] for k in ('path','sha256')},p;return p
old=checked(plan['producer']);text=old.read_text();before="reference = probe.grasp_trial_reference(facade, spec['source_symbol']) if spec['mode'] == 'pick' else None";after="reference = facade.grasp_reference(spec['source_symbol']) if spec['mode'] == 'pick' else None"
assert text.count(before)==1
new=root/'evaluate_bounded_training_candidate_default63_r2_20261024.py';new.write_text(text.replace(before,after))
old_probe=(source/'scripts/probe_bounded_hybrid_d2.py').read_text()
assert 'def grasp_trial_reference' not in old_probe and 'reference_grasp = (facade.grasp_reference(' in old_probe
module=ast.parse(old_probe);exports={'__file__'}
for node in module.body:
 if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):exports.add(node.name)
 if isinstance(node,(ast.Import,ast.ImportFrom)):
  exports.update(a.asname or a.name.split('.')[0] for a in node.names)
used={n.attr for n in ast.walk(ast.parse(new.read_text())) if isinstance(n,ast.Attribute) and isinstance(n.value,ast.Name) and n.value.id=='probe'}
assert used<=exports,(used-exports)
output=run/'default63_r2';output.mkdir(exist_ok=True)
closed=[];partial=[];errors=[]
for i,job in enumerate(plan['jobs']):
 q=json.loads(checked(job['query']).read_bytes());pointer=run/'default63'/f'closed_{i:03d}.json'
 if pointer.exists():
  raw=json.loads(pointer.read_bytes());x=json.loads(checked(raw).read_bytes());assert x['binding']==q['binding'] and x['registered_query']==job['query']
  (output/pointer.name).write_bytes(pointer.read_bytes());closed.append(i);continue
 resume={}
 for repeat in range(3):
  p=run/'default63'/f'query{i:03d}/trial{repeat}/summary.json'
  if p.exists():
   x=json.loads(p.read_bytes());assert x['binding']==q['binding'] and x['query_id']==q['query_id'] and x['candidate_id']==q['candidate_id'] and x['seed']==job['seed']+repeat*1000
   checked(x['endpoint']);resume[str(repeat)]=ref(p)
 if resume:job['resume_trials']=resume;partial.append({'query':i,'repeats':list(resume)})
 p=run/'default63'/f'query{i:03d}/worker.log'
 if p.exists() and 'AttributeError' in p.read_text():errors.append(ref(p))
plan['producer']=ref(new);plan['resume_from']={'manifest':ref(old_plan),'closed_preserved':closed,'partial_valid_trials_preserved':partial,'old_raw_outputs_retained':str(run/'default63')}
plan['measurement_API_correction']={'before':before,'after':after,'reason':'registered f698 truth code calls facade.grasp_reference; that source exports no newer grasp_trial_reference helper','truth_contract_changed':False}
plan['entry']=ref(root/'run_default63_r2_20261024.py')
pre=run/'preparation/default63_r2';pre.mkdir(exist_ok=False);manifest=pre/'manifest.json';manifest.write_text(json.dumps(plan,indent=2)+'\n')
cpu={'passed':True,'source':plan['source_commit'],'producer_before':ref(old),'producer_after':ref(new),'only_one_measurement_API_line_changed':True,'old_source_truth_line_verified':True,'probe_exports_verified':sorted(used),'missing_probe_exports':sorted(used-exports),'closed_preserved':closed,'partial_valid_trials_preserved':partial,'old_program_errors':errors,'truth_contract_changed':False,'training':False}
(pre/'CPU_API_and_resume.json').write_text(json.dumps(cpu,indent=2)+'\n')
s=(run/'preparation/default63/default63.sbatch').read_text().replace('rd-c3-default63-train3','rd-c3-default63-train3-r2').replace('/run_default63_20261024.py','/run_default63_r2_20261024.py').replace('/preparation/default63/manifest.json','/preparation/default63_r2/manifest.json').replace('/default63\n','/default63_r2\n')
job=pre/'default63_r2.sbatch';job.write_text(s)
print(json.dumps({'closed':len(closed),'partial':partial,'program_errors':len(errors),'API_checked':True}))
print(subprocess.check_output(['sbatch',str(job)],text=True).strip())
