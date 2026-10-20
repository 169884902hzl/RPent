"""Legacy replay cannot pair constructor images with restored robot state."""
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from rpent.session import EnvState
from rpent.session.base import StepRecord


def helper(name='restore_legacy_public_frames'):
    root=Path(__file__).resolve().parents[4]
    spec=importlib.util.spec_from_file_location('zero_collision_replay',
        root/'coordination/bounded_skills_20261016/scripts/run_zero_step_collision_forks_20261021.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return getattr(module,name)


@pytest.fixture
def legacy(tmp_path):
    robot=dict(eef_xyz_m=[.1,.2,.3],eef_quat_xyzw=[0.,0.,0.,1.],gripper_opening_m=.08)
    state=dict(robot0_eef_pos=robot['eef_xyz_m'],robot0_eef_quat=robot['eef_quat_xyzw'],
        robot0_gripper_qpos=[.04,-.04])
    original=EnvState(tmp_path/'original')
    original._steps=[StepRecord(0,{}),StepRecord(1,state)]
    original.save('agentview_world_high.npz',np.array([[[.1,.2,.3]]]),step=1)
    artifact=original._artifact_file('agentview_world_high.npz',1)
    prefix=tmp_path/'prefix.json'
    prefix.write_text(json.dumps({'capture_step':1,'records':[r.to_blob() for r in original._steps]}))
    ref=dict(prefix={'path':str(prefix),'sha256':hashlib.sha256(prefix.read_bytes()).hexdigest()},
        capture_step=1,artifacts=[{'name':'agentview_world_high.npz','path':str(artifact),
            'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest()}])
    store=EnvState(tmp_path/'owned/artifacts');store._steps=[StepRecord(0,{'reset_image':True})]
    return SimpleNamespace(_state=store),ref,robot,artifact


def test_matching_saved_frames_replace_reset_cursor_and_preserve_original_bytes(legacy):
    toolkit,ref,robot,original=legacy;before=original.read_bytes()
    proof=helper()(toolkit,ref,robot)
    assert proof['capture_step']==1 and proof['public_pose_match']
    assert toolkit._state.latest_step==1
    assert np.array_equal(toolkit._state.load('agentview_world_high.npz'),[[[.1,.2,.3]]])
    toolkit._state.save('agentview_world_high.npz',np.zeros((1,1,3)))
    assert original.read_bytes()==before


def test_mismatched_pose_rejects_before_replacing_live_state(legacy):
    toolkit,ref,robot,_=legacy;robot={**robot,'eef_xyz_m':[.2,.2,.3]}
    with pytest.raises(ValueError,match='does not match restored proprioception'):
        helper()(toolkit,ref,robot)
    assert toolkit._state.latest_step==0


def test_changed_recorded_artifact_is_rejected(legacy):
    toolkit,ref,robot,original=legacy;original.write_bytes(b'changed')
    with pytest.raises(ValueError,match='registered input changed'):
        helper()(toolkit,ref,robot)


def test_fresh_capture_checks_both_views_and_proprioception(legacy):
    toolkit,ref,robot,_=legacy
    helper()(toolkit,ref,robot)
    for camera in ('agentview','wrist'):
        toolkit._state.save(f'{camera}_high.png',np.zeros((2,2,3),dtype=np.uint8))
        toolkit._state.save(f'{camera}_world_high.npz',np.ones((1,1,3)))
    result=helper('verify_fresh_capture')(toolkit,robot,0)
    assert len(result['artifact_sha256'])==4
    assert all(error==0 for error in result['public_pose_errors'].values())
    with pytest.raises(ValueError,match='constructor frame'):
        helper('verify_fresh_capture')(toolkit,robot,1)


def test_fresh_capture_rejects_new_frame_with_stale_pose(legacy):
    toolkit,ref,robot,_=legacy
    helper()(toolkit,ref,robot)
    with pytest.raises(ValueError,match='does not match restored proprioception'):
        helper('verify_fresh_capture')(toolkit,{**robot,'gripper_opening_m':.01},0)
