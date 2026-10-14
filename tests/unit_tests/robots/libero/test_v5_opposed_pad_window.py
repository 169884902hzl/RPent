from robots.libero.v5_grasp_public_tracking import evaluate_opposed_pad_window


def test_enabled_opposed_pad_verifier_rejects_legacy_geometry_before_execution():
    from types import SimpleNamespace
    import pytest
    from robots.libero.v5_runtime import V5Executor

    toolkit=SimpleNamespace(primitives=SimpleNamespace())
    with pytest.raises(ValueError,match='two calibrated static finger_pads'):
        V5Executor(toolkit,SimpleNamespace(),grasp_opposed_pad_window_v1=True,
                   grasp_measurement_calibration={'grip_site_geometry':{}})
    # A setting which does not request this measurement keeps its old contract.
    V5Executor(toolkit,SimpleNamespace(),grasp_measurement_calibration={'grip_site_geometry':{}})


def frame(left,right):
    return {'eef_xyz':[0,0,1], 'public_finger_pad_regions':{'per_view':{'wrist':{
        'current_target_points':True,'pads':[
            {'geom_name':'finger1','points_near_inward_face':left},
            {'geom_name':'finger2','points_near_inward_face':right}]}}}}


def test_one_finger_comotion_does_not_become_positive_opposed_contact():
    assert evaluate_opposed_pad_window([frame(5,0),frame(5,0)])['verified'] is None


def test_contact_disappearance_remains_unmeasured():
    assert evaluate_opposed_pad_window([frame(5,4),frame(5,0)])['verified'] is None


def test_two_fresh_opposed_surface_measurements_are_retained():
    assert evaluate_opposed_pad_window([frame(5,4),frame(3,4)])['verified'] is True


def test_synchronized_dual_view_fuses_complementary_pad_faces():
    split = {'eef_xyz':[0,0,1], 'public_finger_pad_regions':{'per_view':{
        'agentview': {'current_target_points':True,'pads':[
            {'geom_name':'finger1','points_near_inward_face':5},
            {'geom_name':'finger2','points_near_inward_face':0}]},
        'wrist': {'current_target_points':True,'pads':[
            {'geom_name':'finger1','points_near_inward_face':0},
            {'geom_name':'finger2','points_near_inward_face':4}]}}}}
    assert evaluate_opposed_pad_window([split, split])['verified'] is True
