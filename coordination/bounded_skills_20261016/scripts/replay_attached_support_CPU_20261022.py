"""Replay the two captured public route screens in isolated source processes."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import pickle
import subprocess
import sys
import time


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--input', type=Path)
    args = parser.parse_args()
    if args.source:
        sys.path.insert(0, str(args.source))
        from robots.libero import bounded_screen
        with gzip.open(args.input, 'rb') as handle:
            screen, call_args, call_kwargs = pickle.load(handle)
        screen._pose_geometry_cache = {}
        screen._endpoint_ik_cache = {}
        started = time.perf_counter()
        result = screen(*call_args, **call_kwargs)
        print(json.dumps({'source': str(args.source),
            'screen_source_sha256': sha(Path(bounded_screen.__file__)),
            'input': str(args.input), 'input_sha256': sha(args.input),
            'wall_s': time.perf_counter()-started, 'result': result},
            default=lambda x: x.tolist() if hasattr(x, 'tolist') else str(x)))
        return
    rows = []
    for case in ('case001_startup', 'case006_startup'):
        matches = sorted((args.root/case).glob('startup_*/failed_support_routes/00.pkl.gz'))
        if len(matches) != 1:
            raise ValueError(f'{case}: expected exactly one input, found {matches}')
        row = {'case': case, 'training': False, 'physical_replay': False}
        for arm, source in (('before', args.before), ('after', args.after)):
            command = [sys.executable, __file__, '--root', str(args.root),
                '--before', str(args.before), '--after', str(args.after),
                '--output', str(args.output), '--source', str(source), '--input', str(matches[0])]
            result = subprocess.run(command, check=True, text=True, capture_output=True)
            row[arm] = json.loads(result.stdout.strip().splitlines()[-1])
        rows.append(row)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({'scope': 'saved public route input; CPU only',
        'rows': rows}, indent=2)+'\n')
    print(json.dumps({'output': str(args.output), 'sha256': sha(args.output),
        'cases': len(rows)}))


if __name__ == '__main__':
    main()
