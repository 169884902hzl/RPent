"""Keep failed cohorts and prepare an exact-initial repeat of callback-free saves."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

r = Path('/public/home/sunyihan/rpent_libero_eval')
run = r / 'results/bounded_skills/task_ladder_20261025'
reg = json.loads((run / 'feedback_checkpoint_fix_source.json').read_bytes())
src = Path(reg['remote_source'])
oldsrc = r / 'source_blacklist_progress_44faeea5_20261025'
old = run / 'panels5_blacklist_r2'
out = run / 'panels5_feedback_checkpoint_r3'
oldn, newn = run / 'C0_N1_progressfix', run / 'C0_N1_feedback_checkpoint_r3'
oldd, newd = run / 'C0_model_D2_progressfix', run / 'C0_model_D2_feedback_checkpoint_r3'
olds, news = run / 'shared12318_pilot_r2', run / 'shared12318_pilot_r3_final'


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def replace(text):
    replacements = {str(before): str(after) for before, after in (
            (oldsrc, src), (old, out), (oldn, newn), (oldd, newd), (olds, news),
            (run / 'panels5_feedback_checkpoint', out),
            (run / 'C0_N1_feedback_checkpoint', newn))}
    text = re.sub('|'.join(re.escape(value) for value in replacements),
        lambda match: replacements[match[0]], text)
    return text.replace(reg['base_tree'], reg['tree'])


for before, after in ((old, out), (oldn, newn), (oldd, newd)):
    assert not after.exists()
    shutil.copytree(before, after, copy_function=os.link, symlinks=True,
        ignore=shutil.ignore_patterns('results', 'task_board.lock'))
    for path in after.rglob('*'):
        if not path.is_file() or path.suffix not in {'.json', '.jsonl', '.md', '.sbatch'}:
            continue
        if 'common_starts' in path.parts:
            continue
        text = replace(path.read_text())
        if path.suffix == '.json':
            value = json.loads(text)
            if isinstance(value, dict) and ('source_revision' in value or 'jobs' in value):
                value['source_revision'] = ref(src / 'SOURCE_REVISION.json')
                value['schema'] = ref(src / 'rpent/skill_package/schema.json')
                if 'contract' in value:
                    value['contract'] = ref(src / 'rpent/skill_package/contract.py')
                text = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
        path.unlink()
        path.write_text(text)

sys.path.insert(0, str(src))
from robots.libero.bounded_task_board import update_from_results
update_from_results(out)
news.mkdir()
for name in ('run.py', 'run.sh'):
    (news / name).write_text(replace((olds / name).read_text()))
compile((news / 'run.py').read_text(), str(news / 'run.py'), 'exec')
subprocess.run(['bash', '-n', str(news / 'run.sh')], check=True)

q = run / 'unlock_queue_dagger877'
(q / 'tasks_before_feedback_checkpoint.json').write_bytes((q / 'tasks.json').read_bytes())
tasks = json.loads((q / 'tasks.json').read_bytes())
for task in tasks:
    if task['name'].startswith('development') or task['name'] == 'N1_C0':
        task['script'] = replace(task['script'])
    task['script_sha256'] = ref(Path(task['script']))['sha256']
p = q / 'tasks.next.json'
p.write_text(json.dumps(tasks, indent=2) + '\n')
p.replace(q / 'tasks.json')
p = q / 'dispatch.py'
text = replace(p.read_text()).replace("run/'panels5_blacklist_r2'", "run/'panels5_feedback_checkpoint'")
text = text.replace("run/'panels5_feedback_checkpoint'", "run/'panels5_feedback_checkpoint_r3'")
compile(text, str(p), 'exec')
p.write_text(text)
(run / 'failure_blacklist_source_before_feedback_checkpoint.json').write_bytes(
    (run / 'failure_blacklist_source.json').read_bytes())
(run / 'failure_blacklist_source.json').write_text(json.dumps(reg, indent=2) + '\n')
active = json.loads((run / 'active_queue.json').read_bytes())
active.update(source_tree=reg['tree'], development_panel=str(out), shared_repeat=str(news),
    feedback_checkpoint_CPU_job=reg['CPU_job'], tasks_sha256=ref(q / 'tasks.json')['sha256'],
    dispatcher_sha256=ref(q / 'dispatch.py')['sha256'], source_error_archive=str(olds))
(run / 'active_queue.json').write_text(json.dumps(active, ensure_ascii=False, indent=2) + '\n')
record = {'source_tree': reg['tree'], 'CPU_job': reg['CPU_job'], 'panel': str(out),
    'N1': str(newn), 'D2': str(newd), 'shared_repeat': str(news),
    'held_only_new_tasks': list(range(1, 9)) + [40], 'old_held_jobs_untouched': True,
    'program_error_cohort_kept': str(old), 'physical_started': False}
(run / 'feedback_checkpoint_preparation.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record))
