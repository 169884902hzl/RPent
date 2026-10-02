# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Generate cards from explicitly declared successful original expert traces."""

import argparse
import hashlib
import json
import re
from pathlib import Path

from robots.libero.v5_cards import from_successful_trace


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def scene_signature(path):
    """Hash original scene definitions, excluding language, init and goals."""
    text = re.sub(r";[^\n]*", "", Path(path).read_text())
    sections = []
    for name in ("fixtures", "objects", "regions"):
        match = re.search(r"\(\s*:?(" + name + r")\b", text)
        if match is None:
            continue
        start, depth = match.start(), 0
        for i in range(start, len(text)):
            depth += (text[i] == "(") - (text[i] == ")")
            if depth == 0:
                sections.append(" ".join(text[start:i+1].split()))
                break
    if not sections:
        raise ValueError("original BDDL has no scene sections")
    return hashlib.sha256(json.dumps(sections).encode()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--include-registered-counterfactual", action="store_true")
    a = p.parse_args()
    m = json.loads(a.manifest.read_text())
    registry = m["original_target_registry"]
    assert sha(registry["path"]) == registry["sha256"]
    target_registry = json.loads(Path(registry["path"]).read_text())
    tasks = target_registry["tasks"]
    assert sha(target_registry["source_episodes"]) == target_registry["source_episodes_sha256"]
    episodes = json.loads(Path(target_registry["source_episodes"]).read_text())
    results = {r["output"]:r for r in episodes
               if len(r["identity"]) == 3 or a.include_registered_counterfactual}
    configs = {str(Path(e['runtime_config_path']).parent):e for e in target_registry['episodes']}
    a.output.mkdir(parents=True, exist_ok=False)
    selected, missing = {}, []
    for descriptor in m["runtime_logs"]:
        path = Path(descriptor["path"])
        assert sha(path) == descriptor["sha256"]
        episode = results.get(str(path.parent))
        if episode is None:
            continue
        result = episode['result']
        if not result.get("correct_finish") or result.get("provider") != "oracle":
            continue
        if not 10 <= result["seed"] < 40:
            continue
        if result["suite"] not in ("libero_spatial", "libero_object", "libero_goal", "libero_10"):
            raise ValueError("cards may only use original expert tasks")
        base_key = key = f"{result['suite']}/{result['task']}"
        cf_source = None
        config = configs[str(path.parent)]
        assert sha(config['runtime_config_path']) == config['runtime_config_sha256']
        spec_path = json.loads(Path(config['runtime_config_path']).read_text()).get('counterfactual_spec')
        if spec_path:
            assert len(episode['identity']) == 4 and sha(spec_path) == episode['identity'][3]
            spec = json.loads(Path(spec_path).read_text())
            assert spec['original_bddl_sha256'] == tasks[base_key]['bddl_sha256']
            key += '/cf_' + spec['variant_bddl_sha256'][:12]
            cf_source = {'path':spec_path, 'sha256':sha(spec_path),
                         'goal_origin':'registered_original_scene_counterfactual'}
        trace = [json.loads(line) for line in path.read_text().splitlines()]
        if key not in selected or len(trace) < selected[key]["decisions"]:
            card = from_successful_trace(trace, identity={k: result[k] for k in ("suite","task","seed")},
                                         source_sha256=descriptor["sha256"])
            task = tasks[base_key]
            assert sha(task["bddl_path"]) == task["bddl_sha256"]
            card.update(original_scene_sha256=scene_signature(task["bddl_path"]),
                        task_goal_key=key, goal_source=cf_source or {'goal_origin':'original_task'},
                        source_episode_result_sha256=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest(),
                        source_episodes_sha256=target_registry["source_episodes_sha256"])
            selected[key] = {"card":card, "decisions":len(trace)}
    output = []
    for key in dict.fromkeys([*tasks,*selected]):
        if key not in selected:
            missing.append({"task":key, "reason":"no declared correct-finish original oracle trajectory"})
            continue
        path = a.output / (key.replace("/","_t") + ".json")
        path.write_text(json.dumps(selected[key]["card"],indent=2)+'\n')
        output.append({"task":key, "path":str(path.resolve()), "sha256":sha(path),
                       "original_scene_sha256":selected[key]["card"]["original_scene_sha256"]})
    report = {"version":"category-card/1", "origin":"original_oracle", "files":output,
              "input_manifest":str(a.manifest), "input_manifest_sha256":sha(a.manifest),
              "missing_tasks":missing, "coordinates_in_steps":False, "PRO_inputs_used":False,
              "RPent_cards_in_training":False, "script_sha256":sha(__file__)}
    report['registered_counterfactual_cards'] = sum('/cf_' in item['task'] for item in output)
    (a.output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'cards':len(output),'missing':len(missing),'manifest_sha256':sha(a.output/'manifest.json')}))


if __name__ == "__main__":
    main()
