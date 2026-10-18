"""Append the current measured-source notice and verify only the new slice."""

import argparse
import fcntl
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path('/public/home/sunyihan/rpent_libero_eval')
base = root/'coordination/bounded_skills_20261016'
parser = argparse.ArgumentParser()
parser.add_argument('--receipt-name', default='guided_payload_coord_append_20261018.json')
parser.add_argument('--note', type=Path)
args = parser.parse_args()
note = args.note or base/'progress_guided_payload_20261018.md'
message = ('\n[Codex3 | '+datetime.now(ZoneInfo('America/Los_Angeles')).isoformat()
    +' | public payload identity / node02 cap3]\nCodex1/Codex2: '+note.read_text()+'\n')
raw = message.encode()
path = Path('/public/home/sunyihan/rd_instruction_20260923/COORDINATION.md')
with path.open('ab') as stream:
    fcntl.flock(stream, fcntl.LOCK_EX)
    stream.seek(0, 2)
    start = stream.tell()
    stream.write(raw)
    stream.flush()
    end = stream.tell()
receipt = {'path': str(path), 'append_start': start, 'append_end': end,
    'appended_bytes': len(raw), 'appended_sha256': hashlib.sha256(raw).hexdigest()}
with path.open('rb') as stream:
    stream.seek(start)
    assert hashlib.sha256(stream.read(end-start)).hexdigest() == receipt['appended_sha256']
(base/'reports'/args.receipt_name).write_text(json.dumps(receipt, indent=2)+'\n')
print(json.dumps(receipt))
