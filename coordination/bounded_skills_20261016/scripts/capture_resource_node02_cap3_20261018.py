"""Capture current queue and render its terminal text without changing jobs."""
import json
import re
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

command = ["ssh", "gpu5880-ts", "squeue -h -u sunyihan -o '%i|%j|%T|%N|%R'"]
raw = subprocess.check_output(command, text=True)
rows = [line.split("|") for line in raw.splitlines()]
ours = [row for row in rows if row[1].startswith("rd-bounded-")]
requirements = {}
for job in sorted({row[0].split('_')[0] for row in ours}):
    detail = subprocess.check_output(['ssh', 'gpu5880-ts', 'scontrol show job '+job+' -o'], text=True)
    node = re.search(r'\bReqNodeList=(\S+)', detail).group(1)
    nice = int(re.search(r'\bNice=(\d+)', detail).group(1))
    assert node == 'node02' and nice == 500, (job, node, nice)
    requirements[job] = {'ReqNodeList': node, 'Nice': nice}
running = Counter(row[3] for row in ours if row[2] == "RUNNING")
assert running.get("node01", 0) == 0, running
assert running.get("node02", 0) <= 3, running
now = datetime.now(ZoneInfo("America/Los_Angeles")).isoformat()
root = Path(__file__).resolve().parents[1]/"reports"
report = {"time_pacific": now, "command": command[-1], "stdout": raw,
    "our_running_by_node": {"node01": running.get("node01", 0), "node02": running.get("node02", 0)},
    "requirements_by_array": requirements,
    "scope": "read-only; all rd-bounded active jobs; protected and held jobs unchanged"}
p = root/"resource_latest_node02_cap3_20261018.json"
p.write_text(json.dumps(report, indent=2)+"\n")
text = "squeue snapshot | "+now+"\n"+"JOB | NAME | STATE | NODE | REASON\n"+"\n".join(" | ".join(r) for r in ours)
fig, ax = plt.subplots(figsize=(16, max(3, len(ours)*.3+1.5)))
ax.axis("off")
ax.text(0, 1, text, ha="left", va="top", family="monospace", fontsize=10)
fig.savefig(p.with_suffix(".png"), dpi=150, bbox_inches="tight")
plt.close(fig)
print(json.dumps({"time_pacific": now, "our_running_by_node": report["our_running_by_node"], "jobs": ours}))
