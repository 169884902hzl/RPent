# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Summarize saved request and refresh profiles without rerunning physics."""
import argparse
import hashlib
import json
import pstats
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--job', default='9024_120')
args = parser.parse_args()
root = Path('/public/home/sunyihan/rpent_libero_eval')
directory, = (root/'results/bounded_skills/feasibility_20261017'/('job'+args.job)).glob('*oracle_k4')
profiles = []
for path in sorted(directory.glob('*.pstats')):
    stats = pstats.Stats(str(path))
    functions = [{'file': key[0], 'line': key[1], 'function': key[2],
        'primitive_calls': value[0], 'calls': value[1], 'self_s': value[2], 'cumulative_s': value[3]}
        for key, value in sorted(stats.stats.items(), key=lambda item: item[1][3], reverse=True)]
    profiles.append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'total_self_s': stats.total_tt, 'top15': functions[:15],
        'project_top15': [row for row in functions if '/robots/libero/' in row['file']][:15]})
episodes_path = directory.parent/'episodes.jsonl'
episode, = [json.loads(line) for line in episodes_path.read_text().splitlines()
            if json.loads(line)['arm'] == 'oracle_k4']
choices = directory/'choices.jsonl'
report = {'job': args.job, 'profiles': profiles,
    'episode_ledger': {'path': str(episodes_path), 'sha256': hashlib.sha256(episodes_path.read_bytes()).hexdigest()},
    'choices': {'path': str(choices), 'sha256': hashlib.sha256(choices.read_bytes()).hexdigest()},
    'wall_time_breakdown': episode['wall_time_breakdown'],
    'scope': 'saved cProfile and exclusive wall spans; no new simulation',
    'limitations': ['Cumulative function times overlap and must not be added.',
        'Client RPC profiles include server and transport waiting; they do not isolate SAM kernels.'],
    'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'gpu_used': False, 'physics_steps': 0, 'training': False}
output = root/'coordination/bounded_skills_20261016/reports'/f'profile_saved{args.job}_CPU_20261018.json'
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'output': str(output), 'profiles': [{'name': Path(row['path']).name,
    'total_self_s': row['total_self_s']} for row in profiles]}))
