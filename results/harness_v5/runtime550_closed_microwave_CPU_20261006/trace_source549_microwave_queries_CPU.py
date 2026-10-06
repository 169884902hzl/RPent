"""Trace the frozen SOURCE549 query contract with empty mocked SAM replies."""
import hashlib
import inspect
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from robots.libero.v5_runtime import MeasuredScene, V5Executor, category, scene_vocabulary
from robots.libero.v5_state import Entity

ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
DEST = ROOT / 'results/harness_v5/runtime550_closed_microwave_CPU_20261006'
SOURCE = ROOT / 'source_v5_runtime549_20261006'
MANIFEST = ROOT / 'results/harness_v5/fixture540_measured_handle_selection/preparation_runtime549_smoke30/fixtures_measured_handle_selection.json'
EXPECTED_MANIFEST_SHA = '8db78a69313c4b85468887a60cc103506119313c16a73940070d051e86eb43c6'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


assert sha(MANIFEST) == EXPECTED_MANIFEST_SHA
manifest = json.loads(MANIFEST.read_text())
base_path = Path(manifest['base_config']['path'])
assert sha(base_path) == manifest['base_config']['sha256']
base = json.loads(base_path.read_text())
condition_name, condition = next(iter(manifest['conditions'].items()))
config = {**base, **condition.get('overrides', {})}
flags = {name: config[name] for name in inspect.signature(MeasuredScene).parameters
         if name in config and name not in {'toolkit', 'rpc', 'seed'}}
effective_recovery_flags = {name: config.get(name, inspect.signature(V5Executor).parameters[name].default)
    for name in ('articulate_view_retreat_v1', 'view_retreat_v2', 'retreat_clearance_v1')}
explicit = json.loads((DEST / 'explicit8_public_cases.json').read_text())
records = []
for row in explicit['records']:
    episode = Path(row['episode'])
    states = json.loads((episode / 'states.json').read_text())
    state0 = next(item for item in states['steps'] if item['step_idx'] == 0)
    state1 = next(item for item in states['steps'] if item['step_idx'] == 1)
    registered = set(state1['artifacts'])
    names = state0['state']['object_names']
    instruction = state0['extras']['task_language']
    queries = []

    def load(name):
        assert name in registered
        path = episode / name / ('01.json' if name.endswith('.json') else '01.npz')
        if name.endswith('.json'):
            return json.loads(path.read_text())
        with np.load(path) as data:
            return data[data.files[0]]

    def load_bytes(name):
        assert name in registered
        return (episode / name / '01.png').read_bytes()

    def call(method, kwargs, timeout_s):
        queries.append({'method': method, 'prompt': kwargs.get('text_prompt'),
                        'min_score': kwargs.get('min_score'),
                        'image_sha256': hashlib.sha256(__import__('base64').b64decode(kwargs['image_base64'])).hexdigest()})
        return {'instances': []}

    state = SimpleNamespace(latest_step=1, load=load, load_bytes=load_bytes)
    scene = MeasuredScene(SimpleNamespace(_state=state), SimpleNamespace(call=call), 0, **flags)
    scene.entities = {item['id']: Entity(**{key: item[key] for key in
        ('id', 'name', 'xyz', 'lower', 'upper', 'visible', 'source_step', 'part_of', 'geometry')})
        for item in row['public_before']['entities']}
    scene.instruction = instruction
    scene.instance_limits = Counter(category(name) for name in names)
    vocabulary = scene_vocabulary(names, instruction)
    scene.vocabulary = set(vocabulary)
    scene.refresh(['microwave'])
    records.append({'case': row['case'], 'scene_input_object_names': names,
        'public_instruction': instruction, 'derived_vocabulary': vocabulary,
        'source549_scene_flags': flags, 'queries': queries,
        'work_surface_available': scene.work_surface_measurement is not None,
        'empty_reply_parent_visible': any(item.visible and item.name == 'microwave' for item in scene.entities.values())})
report = {'scope': 'Offline public-camera trace of SOURCE549 query/control contract. '
          'SAM responses are deliberately empty fakes; this is not a detector or skill result. '
          'It proves which queries execute and that absent current measurements do not promote cached parents.',
          'source': {'path': str(SOURCE), 'commit': '8b45399594355c79c2abe6c76a8badab010b8de4',
                     'archive_sha256': '9e5992db560397557ddce8c4c3836dfde8530097399be54e9da86f1e50d8bf5c',
                     'runtime_sha256': sha(SOURCE / 'robots/libero/v5_runtime.py')},
          'manifest': {'path': str(MANIFEST), 'sha256': sha(MANIFEST)},
          'condition': condition_name, 'effective_recovery_flags': effective_recovery_flags,
          'scene_default_flags_not_overridden': {name: inspect.signature(MeasuredScene).parameters[name].default
              for name in ('instruction_queries_v1', 'wrist_recall_v1') if name not in flags},
          'records': records}
destination = DEST / 'source549_microwave_query_contract_CPU.json'
destination.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'report': str(destination), 'sha256': sha(destination), 'flags': flags,
    'case_count': len(records), 'effective_recovery_flags': effective_recovery_flags,
    'first_queries': records[0]['queries'],
    'all_query_prompts': sorted({item['prompt'] for row in records for item in row['queries']}),
    'cached_parent_promoted_with_empty_reply': sum(row['empty_reply_parent_visible'] for row in records)}))
