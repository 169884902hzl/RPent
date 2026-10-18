"""Pair the same synthetic feedback lag against the saved and current executor."""
import hashlib
import json
import runpy
import subprocess
import sys
from types import ModuleType
from pathlib import Path

import numpy as np

from robots.libero import bounded_motion
from coordination.bounded_skills_20261016.scripts.audit_smooth_joins_20261018 import audit_motion

root = Path(__file__).resolve().parents[3]
fake = runpy.run_path(str(root/'tests/unit_tests/robots/libero/test_bounded_motion.py'))['FakePrimitives']
old_source = subprocess.check_output(['git', 'show',
    '9a1de6849fbd4084821ca0c44b7bcd4edc7d92f6:robots/libero/bounded_motion.py'], cwd=root, text=True)
before = ModuleType('bounded_motion_before_brakejoin')
sys.modules[before.__name__] = before
exec(compile(old_source, '9a1de68/robots/libero/bounded_motion.py', 'exec'), before.__dict__)
rows = []
for tag, module in (('before_9a1de68', before), ('after_working_tree', bounded_motion)):
    p = fake()
    p._step_env = lambda action: setattr(p.env, 'position', p.env.position+action[:3]*.05*.3)
    checks = []
    def contact(_):
        checks.append(True)
        return len(checks) == 6
    motion = module.SmoothMotion(p, lambda poses: {'passed': True},
        module.MotionConfig(tracking_error_stop_m=.2))
    result = motion.run([{'xyz_m': [.1, 0., 1.]}], contact_stop=contact)
    audit = audit_motion(result)
    rows.append(dict(version=tag, steps=result['steps_used'], stop=result['stop_reason'],
        brake_completed=result['braking'].get('completed'),
        next_reference_source=motion._reference_start(None)[2], **audit))
assert rows[0]['braking']['reference_translation_acceleration_jump'] > 1e-4
assert rows[1]['braking']['reference_translation_acceleration_jump'] < 1e-12
assert rows[1]['braking']['reference_position_jump_m'] < 1e-12
report = dict(scope='CPU synthetic feedback-lag reproduction; not physical validation',
    reference_before='9a1de6849fbd4084821ca0c44b7bcd4edc7d92f6',
    source_sha256_before=hashlib.sha256(old_source.encode()).hexdigest(),
    source_sha256_after=hashlib.sha256(Path(bounded_motion.__file__).read_bytes()).hexdigest(),
    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    training=False, controls_to_simulator=0, rows=rows)
output = root/'coordination/bounded_skills_20261016/reports/brake_reference_pair_CPU_20261018.json'
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report))
