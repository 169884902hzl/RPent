"""CPU-only assessment of explicitly registered original stove3679 observations."""

from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from robots.libero.v5_fixture_parts import measured_stove_control_pose
from robots.libero.v5_perception_geometry import same_segmented_instance
from robots.libero.v5_state import Entity


ROOT = Path('/public/home/sunyihan/rpent_libero_eval')
JOB = ROOT / 'results/harness_v5/stove523_fullchunks_original_20261005/probe_job3679'
MANIFEST = ROOT / 'results/harness_v5/stove523_fullchunks_original_20261005/preparation/stove_control_fullchunks.json'
OUTPUT = ROOT / 'results/harness_v5/stove551_off_endpoint_CPU_20261006/control3679_assessment.json'
EXPECTED_MANIFEST_SHA = '14e3dbde9930393a0961ec3a6c181859f800a78b725947dbc9a8fe7061445812'


def identity(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


checked = {}


def referenced(ref):
    path = Path(ref['path'])
    actual = identity(path)
    if actual['sha256'] != ref['sha256']:
        raise ValueError(f'recorded input changed: {path}')
    checked[str(path)] = actual
    return path


assert identity(MANIFEST)['sha256'] == EXPECTED_MANIFEST_SHA
plan = json.loads(MANIFEST.read_text())
assert [case['episode'] for case in plan['cases']] == [
    {'suite': 'libero_goal', 'task': 7, 'seed': seed} for seed in range(10)]
observations, ledgers, accepted_by_label = [], [], Counter()
for part in range(4):
    ledger = JOB / f'part{part}' / 'episodes.jsonl'
    ledgers.append(identity(ledger))
    episodes = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
    assert [episode['case'] for episode in episodes] == plan['cases'][part::4]
    for episode in episodes:
        for phase in episode['phases']:
            for stage in ('pre_recovery', 'post_recovery'):
                refs = phase[stage]
                packet = json.loads(referenced(refs['public_measurements']).read_text())
                assert packet['source_step'] == refs['source_step']
                assert not packet['cached_support_used_as_current_visibility']
                shell = packet['current_stove_shell']
                parent = Entity(**{key: shell[key] for key in (
                    'id', 'name', 'xyz', 'lower', 'upper', 'visible', 'source_step')}) if shell else None
                view_results = {}
                for camera, view in packet['views'].items():
                    assert view['source_step'] == packet['source_step']
                    metadata = json.loads(referenced(view['files']['metadata']).read_text())
                    camera_xyz = np.asarray(metadata['extrinsic_cam2world'])[:3, 3]
                    accepted, masks, candidates = [], [], []
                    for query in view['queries']:
                        for instance in query['instances']:
                            cloud_path = referenced(instance['cloud'])
                            mask = np.asarray(Image.open(referenced(instance['mask']))) > 0
                            if any(same_segmented_instance(mask, prior) for prior in masks):
                                candidates.append({'cloud': identity(cloud_path), 'reason': 'same_measured_control_mask'})
                                continue
                            with np.load(cloud_path, allow_pickle=False) as archive:
                                cloud = archive['array']
                            if parent is None:
                                pose, evidence = None, {'reason': 'current_unique_stove_shell_not_measured'}
                            else:
                                pose, evidence = measured_stove_control_pose(cloud, parent, camera_xyz)
                            result = {'query': query['prompt'], 'cloud': identity(cloud_path),
                                      'pose': pose, 'evidence': evidence}
                            if pose:
                                tangent = np.asarray(pose['handle_tangent_xyz'])
                                result['unsigned_tangent_angle_deg_mod180'] = float(
                                    np.degrees(np.arctan2(tangent[1], tangent[0])) % 180)
                                result['xy_tangent_norm'] = float(np.linalg.norm(tangent[:2]))
                                accepted.append(result)
                                masks.append(mask)
                            candidates.append(result)
                    view_results[camera] = {'accepted_instances': len(accepted), 'candidates': candidates,
                                            'unique_current_candidate': accepted[0] if len(accepted) == 1 else None}
                # Truth is read only after public geometry is computed, for
                # diagnostic grouping. It never participates in a pose fit.
                labels = json.loads(referenced(refs['labels']).read_text())
                assert labels['source_step'] == packet['source_step']
                truth = labels['requested_predicates']
                label = {'turn_on': truth['turn_on']['satisfied'], 'turn_off': truth['turn_off']['satisfied'],
                         'qpos': truth['turn_off']['joint_qpos'], 'scope': 'diagnostic_labels_only'}
                record = {'seed': episode['case']['episode']['seed'], 'phase': phase['phase'], 'stage': stage,
                          'source_step': packet['source_step'], 'public_packet': refs['public_measurements'],
                          'views': view_results, 'diagnostic_label': label, 'off_endpoint_proven': False}
                unique = [value['unique_current_candidate'] for value in view_results.values()]
                if all(unique):
                    first, second = unique
                    difference = abs(first['unsigned_tangent_angle_deg_mod180'] - second['unsigned_tangent_angle_deg_mod180'])
                    record['two_view_unsigned_angle_disagreement_deg'] = min(difference, 180 - difference)
                    record['two_view_centre_disagreement_m'] = float(np.linalg.norm(
                        np.asarray(first['pose']['xyz']) - second['pose']['xyz']))
                for camera, value in view_results.items():
                    accepted_by_label[(camera, str(label['turn_off']), value['accepted_instances'])] += 1
                observations.append(record)

paired = [row for row in observations if 'two_view_unsigned_angle_disagreement_deg' in row]
report = {
    'scope': 'Original recorded RGB-D/controls on CPU only; no physics, GPU, PRO tasks, endpoint classifier or qualification',
    'manifest': identity(MANIFEST), 'ledgers': ledgers, 'producer': identity(Path(__file__)),
    'observations': len(observations), 'view_observations': sum(len(row['views']) for row in observations),
    'unique_current_control_views': sum(value['accepted_instances'] == 1 for row in observations for value in row['views'].values()),
    'paired_unique_current_controls': len(paired),
    'accepted_instances_by_diagnostic_off_label': [
        {'camera': camera, 'private_off_label': label, 'accepted_instances': count, 'observations': amount}
        for (camera, label, count), amount in sorted(accepted_by_label.items())],
    'two_view_unsigned_angle_disagreement_deg': [row['two_view_unsigned_angle_disagreement_deg'] for row in paired],
    'independent_off_endpoint_evidence_available': False,
    'gap': [
        'Existing fits return an undirected contact-surface tangent and approach normal, not a signed actuator endpoint or detent.',
        'No publicly measured fixed stove reference axis or certified off-stop reference is supplied to measured_stove_endpoint.',
        'Recorded on/dark colours and private predicate labels cannot provide a runtime off endpoint.',
        'SOURCE544 job4128 three false positives contain no dedicated fixture_control clouds; no control direction was measured by its verifier.'
    ],
    'minimum_wiring_suggestion': [
        'Capture unique same-parent current control masks/clouds before and after action with camera, source_step and SHA, using existing two-view measurement.',
        'Measure a fixed stove reference and a directed control feature/end-stop in RGB-D; retain cross-view disagreement and visibility rather than relying on the PCA sign.',
        'Validate separation of true off and intermediate dark states on independent original-task endpoint measurements before adding any positive off branch.',
        'Until that evidence exists, stable dark visual transitions remain measured receipt facts with endpoint verdict unmeasured.'
    ],
    'observed_records': observations, 'explicit_inputs': list(checked.values()), 'qualification_authorized': False
}
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
print(json.dumps({key: value for key, value in report.items() if key not in ('observed_records', 'explicit_inputs')}, indent=2))
