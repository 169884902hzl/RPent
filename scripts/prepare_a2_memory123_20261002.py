# Copyright 2026 Zhilun Hu.
# SPDX-License-Identifier: Apache-2.0
"""Select original RPent files and recipes from the pinned explicit file receipt."""

import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    for name in ('cohort', 'receipt', 'root', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    receipt = json.loads(a.receipt.read_text())
    cohort = json.loads(a.cohort.read_text())
    names = receipt['files']
    a.output.mkdir(parents=True, exist_ok=False)
    indexes, recipes = [], []
    for ep in cohort['episodes']:
        family, regime = ep['suite'].removeprefix('libero_').rsplit('_',1)
        tag = f'{family}_{regime}_t{ep["task"]}_s0'
        chosen = ['MEMORY.md',f'task-family/task-family_libero{family}_{regime}_t{ep["task"]}.md',
                  f'task-specific/{tag}.json',f'task-specific/{tag}_recipe.jsonl']
        files, missing = [], []
        for name in chosen:
            if name not in names:
                missing.append(name)
                continue
            path = a.root/name
            assert sha(path) == names[name]
            files.append({'name':name,'path':str(path),'sha256':names[name]})
            if name.endswith('_recipe.jsonl'):
                recipes.append({'name':tag,'suite':ep['suite'],'task':ep['task'],
                                'path':str(path),'sha256':names[name]})
        data = {'files':files,'missing_files':missing,'evaluation_only':True,'training_allowed':False,
                'memory_receipt_sha256':sha(a.receipt),'episode':ep,
                'selection':'MEMORY.md + matched task-family + seed0 audit/recipe; no dynamic global-leaf retrieval',
                'source_revision':'7db66088d06d04ae097682332a09704f13e6fc0c'}
        path = a.output/(tag+'_raw_index.json')
        path.write_text(json.dumps(data,indent=2)+'\n')
        indexes.append({'episode':ep,'path':str(path),'sha256':sha(path),'missing_files':missing})
    recipe_index = a.output/'recipe_index.json'
    recipe_index.write_text(json.dumps({'files':recipes,'evaluation_only':True,'training_allowed':False,
                                       'memory_receipt_sha256':sha(a.receipt)},indent=2)+'\n')
    manifest = {'indexes':indexes,'recipe_index':{'path':str(recipe_index),'sha256':sha(recipe_index)},
                'cohort_sha256':sha(a.cohort),'memory_receipt_sha256':sha(a.receipt),
                'evaluation_only':True,'training_allowed':False,'generator_sha256':sha(__file__)}
    (a.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'episodes':len(indexes),'recipes':len(recipes),'manifest_sha256':sha(a.output/'manifest.json')}))


if __name__ == '__main__':
    main()
