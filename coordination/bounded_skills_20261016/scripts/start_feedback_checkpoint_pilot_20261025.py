"""Start the agreed shared repeat after its exact-source CPU panel completes."""
from pathlib import Path
import datetime
import fcntl
import json
import subprocess

r = Path('/public/home/sunyihan/rpent_libero_eval')
run = r / 'results/bounded_skills/task_ladder_20261025'
reg = json.loads((run / 'feedback_checkpoint_fix_source.json').read_bytes())
state = subprocess.check_output(
    ['sacct', '-X', '-j', reg['CPU_job'], '-n', '-o', 'State'], text=True).strip()
assert state == 'COMPLETED', state
assert subprocess.check_output(['squeue', '-j', '12318', '-h', '-o', '%T'],
    text=True).strip() == 'RUNNING'
out = run / 'shared12318_pilot_r3_final'
assert not (out / 'step.log').exists()
# C2 offered this exact four-core step and still owns the parent allocation.
prefix = ['srun', '--jobid=12318', '--overlap', '--exact', '--nodelist=node02',
    '--nodes=1', '--ntasks=1', '--cpus-per-task=4', '--gres=gpu:1']
gpu = subprocess.check_output(prefix + ['nvidia-smi',
    '--query-compute-apps=pid,used_gpu_memory,gpu_uuid', '--format=csv,noheader'], text=True)
(out / 'GPU_before.txt').write_text(gpu)
subprocess.run(['scontrol', 'update', 'JobId=12385', 'ArrayTaskThrottle=2'], check=True)
released = []
for index in [*range(1, 9), 40]:
    job = f'12385_{index}'
    info = subprocess.check_output(['squeue', '-j', job, '-h', '-o', '%T|%R'], text=True).strip()
    if info.startswith('PENDING|') and 'JobHeldUser' in info:
        subprocess.run(['scontrol', 'release', job], check=True)
        released.append(job)
record = {'owner': 'Codex3', 'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'status': 'callback-free same-initial five-world shared repeat starting',
    'source_tree': reg['tree'], 'CPU_job': reg['CPU_job'], 'CPU_state': state,
    'shared_job': 12318, 'shared_step_CPUs': 4, 'episode_processes': 2,
    'C2_service_cancelled': False, 'released_only_own_current_temporary_holds': released,
    'old_held_jobs_untouched': True, 'own_array_throttle': 2,
    'GPU_cap_including_shared': 3, 'training': False,
    'C2_action': 'Same five-world pilot repeats after checkpoint fix. Keep12318 until '
        'separate final switch_ACK; no clean training on shared GPU during pilot.',
    'old_error_cohorts_kept': ['panels5_blacklist_v1', 'panels5_blacklist_r2']}
(out / 'start.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
with Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md').open('a') as f:
    fcntl.flock(f, fcntl.LOCK_EX)
    f.write('\n## Codex3 检查点修正CPU通过，同初态共享试点继续\n\n'
        + json.dumps(record, ensure_ascii=False) + '\n')
try:
    with (out / 'step.log').open('x') as log:
        result = subprocess.run(prefix + ['bash', str(out / 'run.sh')], stdout=log,
            stderr=subprocess.STDOUT)
finally:
    subprocess.run(['scontrol', 'update', 'JobId=12385', 'ArrayTaskThrottle=3'], check=True)
record = {'UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'exit_code': result.returncode, 'own_array_throttle_restored': 3,
    'service12318_cancelled': False}
(out / 'step_exit.json').write_text(json.dumps(record) + '\n')
print(json.dumps(record))
raise SystemExit(result.returncode)
