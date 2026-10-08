"""Append one generated smoke reservation/result to shared coordination."""

import argparse
import fcntl
import json
from pathlib import Path


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--preparation', type=Path, required=True)
    parser.add_argument('--coordination', type=Path, required=True)
    parser.add_argument('--job', type=int)
    parser.add_argument('--summary', type=Path)
    args = parser.parse_args()
    prep = json.loads(args.preparation.read_text())
    job = str(args.job) if args.job else 'not submitted'
    text = ('\n\n## Codex3 microwave identity stop48 development receipt\n\n'
        'Reserve next available 1 GPU; no node binding or dependency. '
        'One previously visited original LIBERO-90 task33/init0, no confirmation, '
        'no training rows. Same immutable source/launcher as capture-only4577. '
        'Stop enabled, max_chunks=48, original measurement thresholds unchanged.\n\n'
        f'Source `{prep["source"]}`, commit `{prep["commit"]}`.\n'
        f'Manifest `{prep["manifest"]["path"]}`, SHA256 `{prep["manifest"]["sha256"]}`.\n'
        f'Output `{prep["run_output"]}`. Same launcher CPU preflight exit0.\n'
        f'Actual job: {job}.\n')
    if args.summary:
        summary = json.loads(args.summary.read_text())
        text += ('\nRetained physical result: ' + json.dumps({key: summary[key] for key in
            ('job', 'status', 'infrastructure_failure', 'wall_s', 'server_chunk_execution',
             'endpoint_candidates', 'temporal_stop_count', 'camera_summary', 'public_receipt')},
            ensure_ascii=True) + '\n'
            f'Public summary `{args.summary}`. Public analysis precedes private diagnosis; '
            'this is a single development trajectory, not qualification.\n')
    with args.coordination.open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.write(text)
        stream.flush()
        fcntl.flock(stream, fcntl.LOCK_UN)
    print(json.dumps({'coordination': str(args.coordination), 'job': job, 'appended_characters': len(text)}))
