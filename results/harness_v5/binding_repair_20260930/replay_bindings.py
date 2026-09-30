#!/usr/bin/env python3
# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Replay explicit, recorded initial measurements without opening a simulator."""

import argparse
import importlib.util
import json
import re
from pathlib import Path

from robots.libero.v5_state import Entity


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("replay_policy", args.policy)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    results = []
    for row in json.loads(args.records.read_text()):
        choice = row["first_choice"]
        context = choice["request"]["context"]
        phrase = json.loads(context.splitlines()[0].removeprefix("instruction "))
        source_phrase = re.split(r" and (?:place|put)| then |,", phrase, maxsplit=1)[0]
        label = re.sub(r"^pick up the ", "", source_phrase)
        label = re.split(r" next to | between | on | in | from ", label)[0]
        axes = tuple(
            tuple(json.loads(re.search(rf"{key}=(\[.*?\])", context)[1]))
            for key in ("right_world", "front_world")
        )
        entities = [
            Entity(**{k: v for k, v in e.items() if k not in ("src", "extent")})
            for e in choice["measurements"]
        ]
        entity = module.OriginalOraclePolicy(None).bind(
            label, entities, source_phrase, axes
        )
        results.append(
            {
                "episode": row["episode"],
                "instruction": phrase,
                "binding": entity.id if entity else None,
                "old_selected": choice["selected"],
                "note": "binding diagnosis only; no action or success inferred",
            }
        )
    args.output.write_text(json.dumps(results, indent=2) + "\n")
    print(
        json.dumps(
            {
                "records": len(results),
                "bound": sum(r["binding"] is not None for r in results),
            }
        )
    )


if __name__ == "__main__":
    main()
