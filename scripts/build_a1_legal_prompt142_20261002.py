"""Archive deterministic A1-L prompt filtering and original-only memory."""

import argparse
import hashlib
import json
from pathlib import Path

from robots.libero.legal_prompt import filtered_prompt


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--memory-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    memory = json.loads(args.memory_manifest.read_text())
    if memory["origin"] != "original_oracle" or memory["PRO_inputs_used"]:
        raise ValueError("A1-L requires original-only legal memory")
    args.output.mkdir(parents=True, exist_ok=False)
    variables = {"output_dir": "evaluation_output", "recipe_tag": "current_episode",
                 "memory_dir": "memory", "reference_tag": "unused", "task": "unused"}
    prompt, evidence = filtered_prompt(variables)
    (args.output / "system_prompt.txt").write_text(prompt)
    (args.output / "line_filter.json").write_text(json.dumps(evidence, indent=2))
    texts = ["Legal memory: original LIBERO tasks only; no PRO-derived content."]
    sources = []
    for item in memory["cards"]:
        path = Path(item["path"])
        if sha(path) != item["sha256"]:
            raise ValueError("task card hash changed")
        card = json.loads(path.read_text())
        texts.append("Task type: " + " ; ".join(" ".join(str(step[k]) for k in
            ("skill", "object_category", "target_category", "mode") if k in step) for step in card["steps"]))
        sources.append({"path": str(path), "sha256": sha(path)})
    for name in ("object_skill_cards.json", "failure_lessons.json", "general_rules.txt"):
        item = memory["files"][name]
        path = Path(item["path"])
        if sha(path) != item["sha256"]:
            raise ValueError("memory evidence changed")
        value = json.loads(path.read_text()) if path.suffix == ".json" else path.read_text()
        # Coordinates/episode identifiers belong to provenance, not the handbook.
        public = value.get("profiles", value.get("rules")) if isinstance(value, dict) else value
        texts.append(name + "\n" + json.dumps(public, ensure_ascii=False))
        sources.append({"path": str(path), "sha256": sha(path)})
    (args.output / "memory").mkdir()
    (args.output / "memory/MEMORY.md").write_text("\n\n".join(texts) + "\n")
    manifest = {"configuration": "A1-L modified RPent", "PRO_memory_used": False,
                "source_memory_manifest_sha256": sha(args.memory_manifest),
                "memory_sources": sources,
                "files": {name: {"path": str(args.output / name), "sha256": sha(args.output / name)}
                          for name in ("system_prompt.txt", "line_filter.json", "memory/MEMORY.md")}}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps({"manifest_sha256": sha(args.output / "manifest.json"),
                      "paragraphs": len(evidence["paragraph_line_mapping"]),
                      "deleted": sum(p["action"] == "delete" for p in evidence["paragraph_line_mapping"])}))


if __name__ == "__main__":
    main()
