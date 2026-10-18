"""Append one exact progress note and verify only its newly written bytes."""
import argparse
import fcntl
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

parser = argparse.ArgumentParser()
parser.add_argument('--note', type=Path, required=True)
parser.add_argument('--receipt', type=Path, required=True)
args = parser.parse_args()
assert not args.receipt.exists()
stamp = datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()
raw = ('\n[Codex3 | '+stamp+' | bounded chunk v2]\n').encode()+args.note.read_bytes()+b'\n'
path = Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md')
with path.open('ab') as stream:
    fcntl.flock(stream, fcntl.LOCK_EX)
    stream.seek(0, 2)
    start = stream.tell()
    stream.write(raw)
    stream.flush()
    end = stream.tell()
digest = hashlib.sha256(raw).hexdigest()
with path.open('rb') as stream:
    stream.seek(start)
    assert hashlib.sha256(stream.read(end-start)).hexdigest() == digest
report = {'path': str(path), 'time_pacific': stamp, 'append_start': start, 'append_end': end,
    'appended_sha256': digest, 'note': str(args.note), 'note_sha256': hashlib.sha256(args.note.read_bytes()).hexdigest()}
args.receipt.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report))
