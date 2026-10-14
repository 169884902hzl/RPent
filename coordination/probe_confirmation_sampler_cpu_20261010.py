"""Separate random-placement startup stalls from RGB-D rendering; no skill runs."""
import faulthandler
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
PLAN = ROOT / 'results/harness_v5/geometric_grasp_confirmation_20261010_r1/bowl/preparation/confirmation.json'
FAULTS = ROOT / 'coordination/confirmation_env_reset_faults_20261010_r1.json'
OUT = ROOT / 'coordination/confirmation_sampler_cpu_probe_20261010_r1'


def main():
    plan = json.loads(PLAN.read_text())
    cases = {c['name']: c for c in plan['cases']}
    if len(sys.argv) > 1:
        case = cases[sys.argv[1]]
        sys.path.insert(0, plan['source_path'])
        faulthandler.dump_traceback_later(30, repeat=True)
        from libero.libero.envs.env_wrapper import ControlEnv
        from robots.libero.v5_reset_seed import attach_reset_seed
        start = time.monotonic()
        env = ControlEnv(bddl_file_name=case['bddl']['path'], use_camera_obs=False,
                         has_offscreen_renderer=False, has_renderer=False,
                         camera_depths=True, camera_heights=256, camera_widths=256,
                         ignore_done=True, horizon=10015)
        print(json.dumps({'constructor_s': time.monotonic() - start}), flush=True)
        env = attach_reset_seed(env)
        env.seed(case['episode']['seed'])
        start = time.monotonic()
        env.reset()
        print(json.dumps({'reset_s': time.monotonic() - start,
                          'camera_rendering': False, 'skill_executed': False}), flush=True)
        env.close()
        return
    OUT.mkdir(exist_ok=False)
    for fault in json.loads(FAULTS.read_text()):
        with (OUT / (fault['case'] + '.log')).open('x') as log:
            try:
                result = subprocess.run([sys.executable, str(Path(__file__)), fault['case']],
                    stdout=log, stderr=subprocess.STDOUT, timeout=240)
                print(json.dumps({'case': fault['case'], 'exit_code': result.returncode}), flush=True)
            except subprocess.TimeoutExpired:
                print(json.dumps({'case': fault['case'], 'timed_out': True}), flush=True)


if __name__ == '__main__':
    main()
