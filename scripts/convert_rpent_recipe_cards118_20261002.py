# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Deterministically convert explicit recipes; unmappable moves stay reported."""

import argparse
import hashlib
import json
import re
from pathlib import Path

from robots.libero.v5_cards import VERSION, validate_card
from robots.libero.v5_runtime import category


def convert(commands):
    steps, unmapped = [], []
    for index, command in enumerate(commands):
        tool = command.get("action")
        if tool in ("release", "retreat", "finish"):
            steps.append({"skill":tool})
        elif tool == "pi0_pick":
            prompt = command.get("prompt", "").lower()
            match = re.fullmatch(r"(?:pick up|pick|grasp) (?:the )?([a-z _-]+)", prompt)
            if match and not any(x in match[1] for x in (" and ", " from ", " below ", " on ")):
                steps.append({"skill":"grasp", "object_category":category(match[1]), "mode":"direct"})
            else:
                unmapped.append({"line":index+1,"reason":"compound or absent grasp category","command":command})
        else:
            unmapped.append({"line":index+1,"reason":"no category-only typed skill mapping; coordinates discarded","command":command})
    return steps, unmapped


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--index",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    index=json.loads(a.index.read_text())
    a.output.mkdir(parents=True,exist_ok=False)
    converted=[]
    for descriptor in index["files"]:
        path=Path(descriptor["path"])
        actual=hashlib.sha256(path.read_bytes()).hexdigest()
        if actual!=descriptor["sha256"]:
            raise ValueError("recipe changed")
        commands=[json.loads(line) for line in path.read_text().splitlines()]
        steps,unmapped=convert(commands)
        # Partial cards are never silently treated as complete recipes.
        card={"version":VERSION,"origin":"rpent_eval","steps":steps,
              "source_sha256":actual,"unmapped":unmapped,"complete_mapping":not unmapped,
              "evaluation_only":True}
        if steps:
            validate_card(card)
        destination=a.output/(descriptor["name"]+'.json')
        destination.write_text(json.dumps(card,indent=2)+'\n')
        converted.append({"path":str(destination.resolve()),"sha256":hashlib.sha256(destination.read_bytes()).hexdigest(),
                          "mapped_steps":len(steps),"unmapped_steps":len(unmapped),"complete_mapping":not unmapped})
    report={"files":converted,"evaluation_only":True,"training_allowed":False,
            "index_sha256":hashlib.sha256(a.index.read_bytes()).hexdigest()}
    (a.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':
    main()
