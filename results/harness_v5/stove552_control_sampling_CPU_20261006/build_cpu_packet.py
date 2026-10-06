"""Prepare explicit original stove measurement inputs; never submit or run physics."""

import hashlib
import json
from pathlib import Path

import numpy as np

from robots.libero.v5_state import Entity
from robots.libero.v5_stove_measurement import measure_stove_control_features
from scripts.probe_v5_stove521_endpoint import CONTROL_FEATURE_QUERIES, validate_manifest


BASE = Path('results/harness_v5/stove552_control_sampling_CPU_20261006')
PARENT = Path('results/harness_v5/stove523_fullchunks_original_20261005/preparation/stove_control_fullchunks.json')
SOURCE_FILES = ['robots/libero/v5_stove_measurement.py', 'scripts/probe_v5_stove521_endpoint.py',
                'robots/libero/v5_stove_probe_env.py', 'robots/libero/v5_fixture_parts.py']


def identity(path):
    path = Path(path)
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


parent = json.loads(PARENT.read_text())
assert identity(PARENT)['sha256'] == '14e3dbde9930393a0961ec3a6c181859f800a78b725947dbc9a8fe7061445812'
sampling = {**parent, 'version': 'original-stove-control-measurement/3-directed-control-dev',
    'purpose': 'Original fixed on/off measurement with separately bound current control and stove reference features',
    'parent_measurement_manifest': identity(PARENT), 'stove_control_features_v1': True,
    'control_feature_queries': dict(CONTROL_FEATURE_QUERIES),
    'required_probe_sha256': identity('scripts/probe_v5_stove521_endpoint.py')['sha256'],
    'required_stove_module_sha256': identity('robots/libero/v5_stove_measurement.py')['sha256'],
    'measurement_stages': ['before_contact', 'pre_recovery_after_contact', 'post_recovery_after_release_retreat'],
    'planned_measurement_captures': 80, 'planned_view_captures': 160,
    'direction_semantics': 'Separate public pivot-to-tip and shell-to-front-edge measurements, otherwise null; no endpoint calibration',
    'private_labels': 'Separate labels.json only; no geometry, stop, action or binding decisions use private qpos/predicates',
    'all_physical_attempts_retained': True, 'new_training_rows': 0, 'qualification_authorized': False,
    'final_source_snapshot': 'root will register a new immutable snapshot; existing snapshots unchanged',
    'launcher_status': 'CPU manifest validated; use a new launcher pointing explicitly to this manifest, not the hardcoded stove523 launcher'}
validate_manifest(sampling)
(BASE / 'stove_control_sampling10.json').write_text(json.dumps(sampling, indent=2) + '\n')

proposal = {
    'version': 'original-stove-nearzero-physical-selection-proposal/1',
    'status': 'prepare-only proposal; fixed-prefix/reset-method driver extension needed before running',
    'input_cases': sampling['cases'], 'scene_family': 'LIBERO-original only',
    'state_selection': 'All ten explicit original Goal7 init0-9; no selection by model score, skill outcome or verifier verdict',
    'methods': ['original off subtask from publicly recorded initial robot posture',
                'current measured control approach followed by the same original off subtask'],
    'off_prefix_chunks': [1, 4, 16, 64, 160], 'actions_per_chunk': 5,
    'experimental_cells': 100, 'fresh_reset_per_cell': True,
    'snapshot_schedule': 'For every method x initial-state x fixed prefix, retain before contact, after fixed prefix and after public release/retreat; do not choose capture times by private qpos',
    'private_postcollection_bins': [
        {'name': 'nearzero_true_off', 'definition': 'official turnoff=true and -0.005 <= private qpos < 0', 'minimum_distinct_observations_target': 20},
        {'name': 'intermediate_dark', 'definition': 'official turnoff=false and 0 <= private qpos <= 0.05 and official turnon=false', 'minimum_distinct_observations_target': 20},
        {'name': 'other', 'definition': 'Every remaining retained observation; no deletion'}],
    'public_feature_analysis': 'Compare observed directed features and uncertainty across private bins only after collection; no off=True branch from extrapolation',
    'insufficient_coverage': 'Report actual bin counts; this selection does not qualify the endpoint. Further development uses another explicit fixed protocol, retaining this batch.',
    'confirmation': 'Independent original initial states and frozen feature rules required; this proposal consumes no confirmation states',
    'private_labels_policy': 'qpos/predicates are diagnostic labels only, never execution/binding/capture selection inputs',
    'training_allowed': False, 'qualification_authorized': False, 'gpu_submitted': False, 'node_binding': None,
}
(BASE / 'nearzero_physical_selection_proposal.json').write_text(json.dumps(proposal, indent=2) + '\n')

cases = json.loads((BASE / 'recorded_control_cases.json').read_text())
results = []
for case in cases:
    for name in ('cloud', 'camera_metadata'):
        assert identity(case[name]['path'])['sha256'] == case[name]['sha256']
    with np.load(case['cloud']['path'], allow_pickle=False) as archive:
        points = archive['array']
    metadata = json.loads(Path(case['camera_metadata']['path']).read_text())
    camera_xyz = np.asarray(metadata['extrinsic_cam2world'])[:3, 3]
    measured = measure_stove_control_features(points, Entity(**case['current_parent']), camera_xyz,
        source_step=case['source_step'], camera='wrist')
    reverse = measure_stove_control_features(points[::-1], Entity(**case['current_parent']), camera_xyz,
        source_step=case['source_step'], camera='wrist')
    assert measured['control_pose'] is not None
    assert measured['directed_lever'] is None and measured['stove_reference'] is None
    assert measured['endpoint_state'] == reverse['endpoint_state'] == 'unmeasured'
    results.append({'name': case['name'], 'cloud': case['cloud'], 'current_measurement': measured,
                    'point_order_reversal_endpoint_state': reverse['endpoint_state'],
                    'original_public_packet': case['original_public_packet'],
                    'private_diagnostic_label': case['private_diagnostic_label']})
report = {'scope': 'CPU replay of explicit real original3679 control clouds; no physics or endpoint qualification',
    'producer': identity(__file__), 'source_files': [identity(path) for path in SOURCE_FILES],
    'real_control_clouds': len(cases), 'current_control_poses_measured': len(cases),
    'directed_levers_measured': 0, 'fixed_stove_references_measured': 0, 'off_endpoints_verified': 0,
    'root_cause': 'Original queries have no separately bound pivot, tip or current stove front-edge measurement; contact PCA is undirected.',
    'results': results, 'sampling_manifest_validation_passed': True,
    'physical_selection_proposal_requires_driver_extension': True,
    'focused_tests': {'passed': 61, 'exit_code': 0,
        'command': '.venv/bin/python -m pytest -q tests/unit_tests/robots/libero/test_v5_stove_measurement.py tests/unit_tests/robots/libero/test_v5_stove521_probe.py tests/unit_tests/robots/libero/test_v5_stove_control_approach.py tests/unit_tests/robots/libero/test_v5_stove_endpoint_receipt.py'},
    'qualification_authorized': False}
(BASE / 'cpu_feature_replay_report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
packet_paths = [BASE / name for name in (
    'README.md', 'build_cpu_packet.py', 'recorded_control_cases.json',
    'stove_control_sampling10.json', 'nearzero_physical_selection_proposal.json',
    'cpu_feature_replay_report.json')]
packet_paths += [Path(case[key]['path']) for case in cases for key in ('cloud', 'camera_metadata')]
changed_files = ['robots/libero/v5_stove_measurement.py', 'scripts/probe_v5_stove521_endpoint.py',
                 'tests/unit_tests/robots/libero/test_v5_stove_measurement.py',
                 'tests/unit_tests/robots/libero/test_v5_stove521_probe.py']
manifest = {'version': 'original-stove-control-sampling-CPU-packet/1',
    'scope': 'Explicit CPU inputs and runnable original measurement manifest; no GPU submitted',
    'files': [identity(path) for path in packet_paths],
    'changed_source_and_tests': [identity(path) for path in changed_files],
    'source_dependencies': [identity(path) for path in SOURCE_FILES if path not in changed_files],
    'parent_manifest': identity(PARENT),
    'data_selection': 'Original Goal7 init0-9 only; five explicit original3679 control clouds for CPU replay',
    'focused_checks_passed': 61, 'private_labels': 'diagnostic only; not consumed by feature functions',
    'training_rows': 0, 'gpu_submitted': False, 'qualification_authorized': False,
    'nearzero_driver_implemented': False}
(BASE / 'manifest.json').write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
print(json.dumps({'sampling_manifest': identity(BASE / 'stove_control_sampling10.json'),
                  'proposal': identity(BASE / 'nearzero_physical_selection_proposal.json'),
                  'report': identity(BASE / 'cpu_feature_replay_report.json'),
                  'packet_manifest': identity(BASE / 'manifest.json')}))
