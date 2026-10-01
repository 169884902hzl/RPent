"""Compare terminal transcript text to captured upstream OpenAI responses."""

import argparse
import hashlib
import json
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("--snapshot", type=Path, required=True)
parser.add_argument("--responses", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
episodes = json.loads(args.snapshot.read_text())
responses = [json.loads(line) for line in args.responses.read_text().splitlines()]
rows = []
for row in episodes:
    episode = row["episode"]
    tag = f"{episode['suite'].removeprefix('libero_')}_t{episode['task']}_s{episode['seed']}"
    transcript = Path(row["output_dir"]) / f"transcript_{tag}.json"
    data = json.loads(transcript.read_text())
    assistants = [m for m in data.get("messages", []) if m.get("role") == "assistant"]
    last = assistants[-1] if assistants else {}
    content = last.get("content", "")
    text = (
        "".join(p.get("text", "") for p in content if isinstance(p, dict))
        if isinstance(content, list)
        else str(content)
    )
    matches = []
    if text:
        for response in responses:
            for choice in response.get("response", {}).get("choices", []):
                message = choice.get("message", {})
                if message.get("content") == text:
                    matches.append({
                        "request_sha256": response["request_sha256"],
                        "unix_s": response["unix_s"],
                        "status_code": response["status_code"],
                        "finish_reason": choice.get("finish_reason"),
                        "message": message,
                        "usage": response["response"].get("usage"),
                    })
    rows.append({
        "episode": episode,
        "physical_success": row["official_success"],
        "terminal_text": text,
        "upstream_exact_text_matches": matches,
        "matched_without_structured_tools": bool(matches) and all(
            not match["message"].get("tool_calls") for match in matches
        ),
        "transcript_sha256": hashlib.sha256(transcript.read_bytes()).hexdigest(),
    })
result = {
    "purpose": "development_interface_diagnostic_not_Table_A",
    "limit": "Captures post-serving-parser API JSON, not pre-parser generated tokens; text-only matching does not establish the parser/generator cause.",
    "source_snapshot_sha256": hashlib.sha256(args.snapshot.read_bytes()).hexdigest(),
    "response_log_sha256": hashlib.sha256(args.responses.read_bytes()).hexdigest(),
    "response_count": len(responses),
    "http400_count": sum(r["status_code"] == 400 for r in responses),
    "max_prompt_tokens": max((r.get("response", {}).get("usage", {}).get("prompt_tokens", 0) for r in responses), default=0),
    "episodes": rows,
}
args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False))
print(json.dumps({k: v for k, v in result.items() if k != "episodes"}, indent=2))
