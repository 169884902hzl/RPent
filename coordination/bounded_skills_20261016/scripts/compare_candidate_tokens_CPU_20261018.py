"""Measure source compaction with the consumer's exact serializer/tokenizer."""
import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--request', type=Path, action='append', required=True)
parser.add_argument('--tokenizer', type=Path, required=True)
parser.add_argument('--consumer-root', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
sys.path.insert(0, str(args.consumer_root/'robot_decider'))
from transformers import AutoTokenizer
from robot_decider.bounded_choice.readout import encode_step_prompt
from robot_decider.bounded_choice.skill_package import SkillPackageBridge
from rpent.skill_package import VERSION
from rpent.skill_package.contract import compact_candidate

bridge = SkillPackageBridge(root/'rpent/skill_package/schema.json')
tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, local_files_only=True)
rows = []
for path in args.request:
    source = json.loads(path.read_text())
    full = copy.deepcopy(source)
    full.update(schema_version=VERSION, execution_prefix=None)
    compact = copy.deepcopy(full)
    compact['candidates'] = [compact_candidate(c) for c in full['candidates']]
    ids = [c['id'] for c in full['candidates']]
    assert ids == [c['id'] for c in compact['candidates']]
    sides = {}
    for name, request in [('full', full), ('compact', compact)]:
        value = bridge.to_model_request(request)
        encoded = encode_step_prompt(tokenizer, value)
        sides[name] = dict(candidates=len(request['candidates']), prompt_tokens=len(encoded.input_ids),
            prompt_sha256=hashlib.sha256(encoded.prompt.encode()).hexdigest(),
            prompt_bytes=len(encoded.prompt.encode()))
    rows.append(dict(source=str(path), source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        candidate_ids=ids, blocked_markers=sum(c['consequences']['screen_scope']=='blocked_at_current_prefix'
            for c in compact['candidates']), **sides,
        tokens_saved=sides['full']['prompt_tokens']-sides['compact']['prompt_tokens']))
report = dict(scope='CPU format/token check; no model inference, no physical execution',
    schema=bridge.identity, tokenizer_files={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in args.tokenizer.iterdir() if p.is_file()},
    consumer_sources={str(p.relative_to(args.consumer_root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (args.consumer_root/'robot_decider/robot_decider/bounded_choice').glob('*.py')},
    rows=rows, training=False, GPU_used=False)
args.output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(rows, indent=2))
