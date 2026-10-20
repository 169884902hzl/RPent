"""Run the requested offline skill/preparation panel with a spawnable entry."""
import os
from pathlib import Path
import subprocess
import sys


def main():
    root=Path(__file__).resolve().parents[3]
    tests=root/'tests/unit_tests/robots/libero'
    # The facade configures GL before any test imports native MuJoCo. The
    # pytest module entry also lets multiprocessing spawn import __main__.
    rgbd=tests/'test_bounded_rgbd.py'
    files=[rgbd,*sorted(p for p in tests.glob('test_bounded_*.py') if p!=rgbd)]
    files.extend(tests/name for name in ('test_v5_branch_state.py','test_v5_grasp_kinematics.py',
        'test_v5_grasp_geometry.py','test_v5_grasp_route.py','test_skill_package_schema.py','test_skill_package_legal.py',
        'test_schema6_physical_launcher.py'))
    env=dict(os.environ,MUJOCO_GL='egl',PYOPENGL_PLATFORM='egl',OPENBLAS_NUM_THREADS='1',
        OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    return subprocess.run([sys.executable,'-m','pytest','-q',*map(str,files)],cwd=root,env=env).returncode


if __name__=='__main__':raise SystemExit(main())
