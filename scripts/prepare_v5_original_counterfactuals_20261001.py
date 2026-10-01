"""Register perception-bound target combinations in explicit original scenes."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import random
from pathlib import Path

from robots.libero.v5_counterfactual import counterfactual_bddl
from robots.libero.v5_runtime import category
from robots.libero.v5_state import Entity, candidates, fixture_actions

PLACEABLE = {"basket", "plate", "rack", "ramekin", "caddy", "frypan", "bowl"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rewrites(source, target, relation):
    phrase = ("into" if relation == "in" else "onto") + " the " + target
    commands = (
        "Put the {source} {phrase}.", "Place the {source} {phrase}.",
        "Move the {source} {phrase}.", "Transfer the {source} {phrase}.",
        "Pick up the {source} and put it {phrase}.",
        "Pick up the {source} and place it {phrase}.",
        "Take the {source} and move it {phrase}.",
        "Grasp the {source}, then put it {phrase}.",
        "Grasp the {source}, then place it {phrase}.",
        "Lift the {source} and transfer it {phrase}.",
    )
    # Reword the same predicate, without adding an unjudged no-disturbance
    # requirement to language that the physical oracle cannot evaluate.
    sentences = [command.format(source=source, phrase=phrase) for command in commands]
    return [prefix + (sentence[0].lower() + sentence[1:] if prefix else sentence)
            for prefix in ("", "Please ", "For this task, ") for sentence in sentences]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.scenes = args.scenes.resolve()
    args.output = args.output.resolve()
    from libero.libero import benchmark, get_libero_path
    from libero.libero.envs.bddl_utils import robosuite_parse_problem

    plan = json.loads(args.scenes.read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    variants, rejected = [], []
    for scene in plan["scenes"]:
        if scene["suite"] not in ("libero_spatial", "libero_object", "libero_goal", "libero_10"):
            raise ValueError("only original task files may be read")
        if not 10 <= scene["seed"] < 40:
            raise ValueError("counterfactual source init must be training-only")
        measured_path = Path(scene["measurements"])
        if sha(measured_path) != scene["measurements_sha256"]:
            raise ValueError("registered perception frame changed")
        measured = json.loads(measured_path.read_text())["entities"]
        entities = [Entity(**{k: e[k] for k in ("id", "name", "xyz", "lower", "upper", "visible", "source_step")})
                    for e in measured if e["src"] == "perception" and e["visible"]]
        counts = collections.Counter(e.name for e in entities)
        task = benchmark.get_benchmark(scene["suite"])().get_task(scene["task"])
        original = Path(get_libero_path("bddl_files")) / task.problem_folder / task.bddl_file
        private = robosuite_parse_problem(str(original))
        symbols = collections.defaultdict(list)
        for kind, names in private["objects"].items():
            symbols[category(kind)].extend(names)
        for obj in entities:
            if fixture_actions(obj.name) or obj.name in PLACEABLE:
                continue
            for target in entities:
                if target.name not in PLACEABLE or target.id == obj.id:
                    continue
                if any(counts[e.name] != 1 or len(symbols[e.name]) != 1 for e in (obj, target)):
                    rejected.append({"scene": scene, "source": obj.name, "target": target.name, "reason": "nonunique_category_binding"})
                    continue
                source_symbol, target_symbol = symbols[obj.name][0], symbols[target.name][0]
                possible = candidates(entities, f"place the {obj.name} in the {target.name}",
                                      (0, 0, 0), obj.id, [], random.Random(0))
                for relation in ("in", "on"):
                    if not any(c.tool == "place" and c.target == target.id and c.mode == relation for c in possible):
                        continue
                    goal_target = target_symbol
                    if relation == "in":
                        regions = [name for name, region in private["regions"].items()
                                   if region["target"] == target_symbol and name.endswith("contain_region")]
                        if len(regions) != 1:
                            continue
                        goal_target = regions[0]
                    goal = [relation, source_symbol, goal_target]
                    wording = rewrites(obj.name, target.name, relation)
                    assert len(wording) == len(set(wording)) == 30
                    instruction = wording[0]
                    changed = counterfactual_bddl(original.read_text(), goal, instruction)
                    digest = hashlib.sha256(changed.encode()).hexdigest()
                    root = args.output / (scene["suite"] + "_t" + str(scene["task"]) + "_" + digest[:12])
                    root.mkdir(exist_ok=False)
                    bddl = root / "variant.bddl"
                    bddl.write_text(changed)
                    spec = {"suite": scene["suite"], "task": scene["task"], "instruction": instruction,
                            "goal": goal, "rewrites": wording, "instruction_sha256": hashlib.sha256(instruction.encode()).hexdigest(),
                            "original_bddl": str(original), "original_bddl_sha256": sha(original),
                            "variant_bddl": str(bddl), "variant_bddl_sha256": sha(bddl),
                            "binding": {"source": obj.id, "target": target.id, "basis": "unique_measured_category"},
                            "source_scene": scene, "PRO_inputs_used": False,
                            "physically_verified": False, "admission": "requires correct-finish physical rollout"}
                    spec_path = root / "spec.json"
                    spec_path.write_text(json.dumps(spec, indent=2) + "\n")
                    variants.append({"spec": str(spec_path), "sha256": sha(spec_path), "goal": goal,
                                     "suite": scene["suite"], "task": scene["task"]})
    report = {"purpose": "preregistered original-scene counterfactual goals, not yet physically admitted",
              "input": str(args.scenes), "input_sha256": sha(args.scenes), "variants": variants,
              "rejected": rejected, "PRO_inputs_used": False, "training_init_indices": list(range(10, 40)),
              "rules": "unique measured graspable category x unique measured placeable region; existing on/in candidates; unchanged scene bytes"}
    (args.output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"registered_variants": len(variants), "rejected_bindings": len(rejected)}))


if __name__ == "__main__":
    main()
