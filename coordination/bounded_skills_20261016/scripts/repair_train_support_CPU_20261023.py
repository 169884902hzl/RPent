"""Complete missing private support interventions from retained integration samples.

No policy actions or hold windows are rerun. Original summaries stay immutable.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pickle
import sys


def ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def checked(item):
    path = Path(item['path'])
    assert ref(path)['sha256'] == item['sha256'], path
    return path


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--shard', type=int, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--limit', type=int)
    a = p.parse_args()
    source = a.root/'source_pi_first_origin_f6ce1d46_20261023'
    base = a.root/'results/bounded_skills/next_b_pi_first_20261023/train_dagger_once_priority1'
    plan_path = base/'preparation'/('pilot32_catalog_r3.json' if a.shard == 0 else f'bulk_shard{a.shard:03d}.json')
    original = base/('pilot32' if a.shard == 0 else f'shard{a.shard:03d}')
    plan = json.loads(plan_path.read_text())
    assert plan['training_split_collection'] and not any(plan[k] for k in ('PRO', 'D2', 'confirmation'))
    a.output.mkdir(parents=True, exist_ok=True)
    assert not (a.output/'manifest.json').exists(), 'completed output already exists'
    os.environ.update(CUDA_VISIBLE_DEVICES='', LIBERO_TYPE='standard',
        LIBERO_CONFIG_PATH=str(checked(plan['libero_config']).parent),
        LIBERO_GRASP_DIAGNOSTIC_MODELS=str(a.output.resolve()/'private_models'),
        MUJOCO_GL='egl', PYOPENGL_PLATFORM='egl', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    sys.path.insert(0, str(source))
    os.chdir(source)
    spec = importlib.util.spec_from_file_location('original_hooks', source/'coordination/bounded_skills_20261016/scripts/shared_gpu_episodes_20261019.py')
    hooks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hooks)
    hooks.bootstrap_source('original', evaluation='hybrid_repair')
    hooks.install_d2_restore_compatibility()
    import numpy as np
    import mujoco
    from libero.libero.envs.env_wrapper import ControlEnv
    from robots.libero import v5_branch_state, v5_grasp_truth as truth_code

    rows = []
    corrected = 0
    for index, job in enumerate(plan['jobs']):
        existing = a.output/f'closed_{index:03d}.json'
        if existing.exists():
            value = json.loads(checked(json.loads(existing.read_text())).read_text())
            if value.get('private_support_completion_of'):
                trial = value['trials'][0]
                completion = trial['result']['private_support_completion']
                rows.append({'index': index, 'old_trial': completion['original_trial'],
                    'corrected_trial': trial['summary'], 'old_success': None,
                    'success': trial['result']['success'],
                    'status': trial['result']['private_truth']['truth_v3']['status'],
                    'max_geometry_error': completion['max_geometry_error'], 'additional_policy_actions': 0})
                corrected += 1
            continue
        pointer = original/f'closed_{index:03d}.json'
        item = json.loads(pointer.read_text())
        report = json.loads(checked(item).read_text())
        result = (report.get('trials') or [{}])[0].get('result', {})
        if report['status'] != 'physical_result' or result.get('success') is not None:
            write(a.output/pointer.name, item)
            continue
        truth = result.get('private_truth', {})
        if not any(s.get('counterfactual_support_evidence', {}).get('reason') ==
                   "counterfactual_batch_failed:KeyError('LIBERO_GRASP_DIAGNOSTIC_MODELS')"
                   for s in truth.get('samples', [])):
            write(a.output/pointer.name, item)
            continue
        query = json.loads(checked(report['registered_query']).read_text())
        snapshot = pickle.loads(checked(query['snapshot']).read_bytes())
        case = job['case']
        assert not case.get('diagnostic', {}).get('own_layout'), 'own layouts require their original construction'
        env = v5_branch_state.attach_branch_state(ControlEnv(bddl_file_name=str(checked(case['bddl'])),
            has_renderer=False, has_offscreen_renderer=False, use_camera_obs=False,
            camera_names=[], ignore_done=True, hard_reset=False, horizon=10015))
        try:
            env.seed(case['episode']['seed'])
            env.reset()
            physics = snapshot['physics']
            # Camera observable caches are intentionally absent in this CPU
            # scorer. Restore fixed furniture transforms, then each complete
            # integration sample; no controller or observation is executed.
            for field, value in physics['actuator_state']['model'].items():
                target = getattr(env.env.sim.model, field)
                assert target.shape == np.asarray(value).shape
                target[:] = value
            native_model, native_data = env.env.sim.model._model, env.env.sim.data._data
            # The exact stored integration state is the registered worker's
            # input. mj_step leaves derived positions one substep behind;
            # compare those saved diagnostics separately, without changing
            # their truth values or substituting newly computed samples.
            updated = copy.deepcopy(truth)
            samples = updated['samples']
            name = updated['reference']['target']
            states = [np.array(s['integration_state']) for s in samples]
            max_geometry_error = 0.0
            refreshed_contact_identity_changes = 0
            for sample, state in zip(samples, states):
                assert len(state) == mujoco.mj_stateSize(native_model, sample['integration_state_spec'])
                mujoco.mj_setState(native_model, native_data, state, sample['integration_state_spec'])
                restored = np.empty_like(state)
                mujoco.mj_getState(native_model, native_data, restored, sample['integration_state_spec'])
                assert np.array_equal(state, restored), 'intervention input changed'
                mujoco.mj_forward(native_model, native_data)
                actual = truth_code.contact_sample(env.env, name)
                for key in ('lower_extent_m', 'target_com_xyz', 'tcp_xyz', 'tcp_rotation_world'):
                    error = float(np.max(np.abs(np.asarray(actual[key])-np.asarray(sample[key]))))
                    max_geometry_error = max(max_geometry_error, error)
                def contacts(value):
                    return sorted((c['geom1'], c['geom2'], c['distance_m']) for c in value['contacts'])
                original_contacts, actual_contacts = contacts(sample), contacts(actual)
                for pair in original_contacts:
                    for geom in pair[:2]:
                        assert env.env.sim.model.geom_name2id(geom) >= 0
                refreshed_contact_identity_changes += int([c[:2] for c in original_contacts] != [c[:2] for c in actual_contacts])
            truth_code.enrich_registered_samples(env.env, name, updated['reference'], samples, states)
            updated['truth_v3'] = truth_code.sustained_grasp_v3(samples, updated['reference'])
            repaired = copy.deepcopy(result)
            repaired.update(success=updated['truth_v3']['success'], private_truth=updated,
                private_support_completion={'original_trial': report['trials'][0]['summary'],
                    'original_window_states_unchanged': True, 'max_geometry_error': max_geometry_error,
                    'model_body_transforms_from_snapshot': query['snapshot'],
                    'refreshed_contact_identity_changes': refreshed_contact_identity_changes,
                    'sample_rule': 'original measured geometry/contact samples retained; only registered intervention rerun on their exact saved integration states',
                    'additional_policy_actions': 0, 'truth_code': ref(source/'robots/libero/v5_grasp_truth.py')})
            out = a.output/f'query{index:03d}'
            out.mkdir()
            write(out/'trial_summary.json', repaired)
            outer = copy.deepcopy(report)
            outer['trials'] = [{'result': repaired, 'summary': ref(out/'trial_summary.json')}]
            outer['private_support_completion_of'] = item
            write(out/'summary.json', outer)
            write(a.output/pointer.name, ref(out/'summary.json'))
            row = {'index': index, 'old_trial': report['trials'][0]['summary'],
                'corrected_trial': ref(out/'trial_summary.json'), 'old_success': None,
                'success': repaired['success'], 'status': updated['truth_v3']['status'],
                'max_geometry_error': max_geometry_error, 'additional_policy_actions': 0}
            rows.append(row)
            print(json.dumps(row), flush=True)
            corrected += 1
        finally:
            env.close()
        if a.limit and corrected >= a.limit:
            break
    write(a.output/'manifest.json', {'shard': a.shard, 'original_manifest': ref(plan_path),
        'corrected_results': str(a.output), 'rows': rows, 'corrected_trials': corrected,
        'partial_probe': bool(a.limit), 'additional_policy_actions': 0,
        'truth_thresholds_unchanged': True, 'source_split': 'train', 'training_executed': False,
        'PRO': False, 'D2': False, 'confirmation': False})


if __name__ == '__main__':
    main()
