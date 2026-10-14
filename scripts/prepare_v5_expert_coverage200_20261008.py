#!/usr/bin/env python3
"""Prepare original200 coverage development using the physically probed snapshot."""
import argparse,json
from pathlib import Path
from prepare_expert_remote_resume_20261008 import packet,ref

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 original=a.root/'coordination/expert_subtask_probe_20261008/manifest/manifest.json'
 index=json.loads(original.read_text());source=index['source_snapshot']
 template=json.loads(Path(index['files'][0]['path']).read_text())
 registered=a.root/'results/harness_v5/interim574_20261007/preparation/registered_original_gate_200.json'
 episodes=json.loads(registered.read_text())['episodes']
 assert len(episodes)==200 and len({(e['suite'],e['task'],e['seed']) for e in episodes})==200
 assert all(e['suite'] in ('libero_spatial','libero_object','libero_goal','libero_10') and 0<=e['seed']<5 for e in episodes)
 template.update(purpose='original200 matching-subtask expert coverage development; not freeze evidence',startup_repair_only=False,confirmation=False,training_allowed=False,behavior_frozen=False)
 audit={'preserved_unique_physical_identities':0,'policy':'new development run; preserve previous 171/200 ledger unchanged','confirmation':False,'training_allowed':False}
 result=packet(a.output.resolve(),episodes,template,index,source,[ref(original),ref(registered),ref(Path(__file__))],8,audit)
 print(json.dumps(result))
if __name__=='__main__':main()
