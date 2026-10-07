"""Wrist ROI guidance cannot manufacture depth support or reuse old evidence."""

import numpy as np
import pytest
from types import SimpleNamespace

from robots.libero.v5_microwave_wrist_roi import fit_wrist_fixed_roi
from robots.libero.v5_verification import vertical_face
from robots.libero.v5_runtime import V5Executor


def reference():
    points = np.array([[x, .25, z] for x in np.linspace(.08, .17, 30) for z in np.linspace(.94, 1.1, 40)])
    record = {**vertical_face(points), 'source': 'perception', 'frame_id': 'world', 'length_unit': 'm',
              'source_cameras': ['agentview'], 'source_step': 3, 'mask_count': 1, 'sha256': 'publicreference'}
    return points, record


def test_wrist_fixed_roi_refits_only_current_wrist_samples():
    cloud, ref = reference()
    wrist = cloud.reshape(30, 40, 3).copy()
    wrist[..., 1] += .002
    fit, evidence, points, mask = fit_wrist_fixed_roi(wrist, ref, cloud, source_step=3)
    assert evidence['status'] == 'measured'
    assert evidence['roi_source_cameras'] == ['agentview'] and evidence['fit_source_cameras'] == ['wrist']
    assert evidence['fit_uses_reference_points'] is False
    assert len(points) == mask.sum() and np.array_equal(points, wrist[mask])
    assert np.isclose(fit['centre'][1], .252)
    assert not np.isclose(fit['centre'][1], ref['centre'][1])


@pytest.mark.parametrize('failure', ['zero_depth', 'occluder', 'stale', 'ambiguous', 'nonpublic'])
def test_unknown_reference_or_unsupported_wrist_depth_stays_unknown(failure):
    cloud, ref = reference()
    wrist = cloud.reshape(30, 40, 3).copy()
    if failure == 'zero_depth':
        wrist[:] = 0
    elif failure == 'occluder':
        wrist[..., 1] -= .03
    elif failure == 'stale':
        ref['source_step'] -= 1
    elif failure == 'ambiguous':
        ref['mask_count'] = 2
    else:
        ref['source'] = 'sim_truth'
    ref.update(solved=True, private_joint_qpos=0.)
    fit, evidence, _, _ = fit_wrist_fixed_roi(wrist, ref, cloud, source_step=3)
    assert fit is None and evidence['status'] == 'unmeasured'


def test_private_labels_never_supply_or_change_roi_fit():
    cloud, ref = reference()
    wrist = cloud.reshape(30, 40, 3)
    before = fit_wrist_fixed_roi(wrist, ref, cloud, source_step=3)
    ref.update(private_joint_qpos=50., solved=False, private_xyz=[9, 9, 9])
    after = fit_wrist_fixed_roi(wrist, ref, cloud, source_step=3)
    assert before[:2] == after[:2]
    assert np.array_equal(before[2], after[2])


def test_wrist_fixed_roi_runtime_switch_defaults_off():
    toolkit = SimpleNamespace(primitives=SimpleNamespace())
    assert V5Executor(toolkit, SimpleNamespace()).microwave_wrist_fixed_roi_v1 is False
    assert V5Executor(toolkit, SimpleNamespace(), microwave_wrist_fixed_roi_v1=True).microwave_wrist_fixed_roi_v1 is True
