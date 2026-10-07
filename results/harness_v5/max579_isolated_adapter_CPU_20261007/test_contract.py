"""CPU-only transport/pose/prefix checks; no simulated success is claimed."""
from pathlib import Path
from types import SimpleNamespace
import json
import sys
import unittest

import numpy as np

from observer_contract import CanonicalObserver, ObservationContractError, eef_transform, resize_nearest
from episode_contract import PairedEpisodeBridge, PairIntegrityError

PACKET = Path(__file__).resolve().parent
REPO = PACKET.parents[2]


def frame(value=20, position=(0, 0, 1), private_xyz=(9, 9, 9)):
    rgb = np.full((6, 8, 3), value, dtype=np.uint8)
    return {"agentview_image": rgb.copy(), "robot0_eye_in_hand_image": rgb.copy()+1,
            "agentview_depth": np.full((6, 8, 1), .5, dtype=np.float32),
            "robot0_eye_in_hand_depth": np.full((6, 8, 1), .6, dtype=np.float32),
            "robot0_eef_pos": np.asarray(position, dtype=float), "robot0_eef_quat": np.array([0, 0, 0, 1.]),
            "robot0_gripper_qpos": np.array([.03, .03]), "bowl_1_pos": np.array(private_xyz),
            "private_goal_done": True, "private_joint": .3, "libero_max_event": {"object": "secret"}}


class Meta:
    def __init__(self):
        self.shift = 0.; self.calls = 0

    def __call__(self, camera, height, width):
        self.calls += 1
        e = np.eye(4); e[0, 3] = self.shift
        if camera == "robot0_eye_in_hand":
            e[2, 3] = 1.1
        return {"camera_name": camera, "height": height, "width": width,
                "intrinsic_K": [[width, 0, width/2], [0, height, height/2], [0, 0, 1]],
                "extrinsic_cam2world": e.tolist(), "depth_near": .01, "depth_far": 10.}


class FakeWrapped:
    def __init__(self):
        self.warmup_steps = self.total_env_steps = 0
        self.runtime = SimpleNamespace(current_instruction="pick up the bowl", applied=False)
        self.init_state_sha256 = "a"*64; self.policy_seed = 7
        self.actions = []; self.queries = []

    def step(self, action):
        self.total_env_steps += 1
        self.actions.append(action)
        if self.total_env_steps == 2:
            self.runtime.applied = True
        return frame(value=20+self.total_env_steps), 0., False, {"libero_max_event": {"private_pose": [1,2,3]}}

    def record_policy_query(self, actions, **kwargs):
        self.queries.append({"policy_step": self.total_env_steps, "actions": np.asarray(actions).tolist(), **kwargs})


def observer(mode="initial_frozen_with_public_wrist_fk"):
    return CanonicalObserver(Meta(), calibration_mode=mode, policy_resolution=8)


class ContractTests(unittest.TestCase):
    def test_transformed_pixels_preserved_no_second_noise_or_render(self):
        o = observer(); raw = frame(17); raw['agentview_image'][1:4,2:5] = 0
        o.accept(raw, control_step=0)
        rgb, depth = o.render_camera(height=12,width=16,depth=True)
        np.testing.assert_array_equal(rgb, resize_nearest(raw['agentview_image'],12,16))
        np.testing.assert_array_equal(depth, resize_nearest(raw['agentview_depth'],12,16))
        np.testing.assert_array_equal(rgb, o.render_camera(height=12,width=16))
        raw['agentview_image'][:] = 255
        self.assertFalse(np.all(o.render_camera(height=12,width=16)==255))

    def test_private_pose_labels_and_event_fields_never_exposed(self):
        a=observer(); b=observer()
        a.accept(frame(private_xyz=(9,9,9)),control_step=0)
        b.accept(frame(private_xyz=(-5,-5,-5)),control_step=0)
        self.assertIsNone(a.raw_obs()['bowl_1_pos'])
        for forbidden in ('private_goal_done','private_joint','libero_max_event'):
            self.assertNotIn(forbidden,a.raw_obs())
        np.testing.assert_array_equal(a.policy_obs('same')['states'],b.policy_obs('same')['states'])

    def test_fresh_measurement_explicitly_versioned_without_controls(self):
        w=FakeWrapped(); captures=[]
        def fresh():
            captures.append(1);return frame(value=22+len(captures))
        bridge=PairedEpisodeBridge(w,observer(),budget_controls=3,fresh_measurement_provider=fresh)
        bridge.initialize(frame())
        first=bridge.raw_obs();second=bridge.raw_obs()
        self.assertEqual(bridge.controls,0);self.assertEqual(w.actions,[])
        self.assertNotEqual(first['agentview_image'][0,0,0],second['agentview_image'][0,0,0])
        self.assertEqual(bridge.observer.frame_records[-1]['capture'],'fresh_transformed_measurement')
        self.assertEqual(bridge.get_camera_meta()['observation_frame_index'],2)

    def test_calibration_configs_separate_and_wrist_uses_public_fk(self):
        frozen_meta=Meta(); live_meta=Meta()
        frozen=CanonicalObserver(frozen_meta,calibration_mode='initial_frozen_with_public_wrist_fk')
        live=CanonicalObserver(live_meta,calibration_mode='live_simulator_calibration')
        frozen.accept(frame(),control_step=0);live.accept(frame(),control_step=0)
        frozen_meta.shift=live_meta.shift=.4
        moved=frame(position=(.2,0,1))
        frozen.accept(moved,control_step=1);live.accept(moved,control_step=1)
        f=frozen.get_camera_meta('agentview',6,8);l=live.get_camera_meta('agentview',6,8)
        self.assertEqual(f['extrinsic_cam2world'][0][3],0.)
        self.assertEqual(l['extrinsic_cam2world'][0][3],.4)
        w=frozen.get_camera_meta('wrist',6,8)
        self.assertAlmostEqual(w['extrinsic_cam2world'][0][3],.2)
        self.assertEqual(frozen_meta.calls,2)

    def test_per_control_event_budget_and_private_info_filter(self):
        w=FakeWrapped(); bridge=PairedEpisodeBridge(w,observer(),budget_controls=3)
        bridge.initialize(frame())
        obs,reward,term,trunc,info=bridge.chunk_step(np.zeros((5,7)),return_all_frames=True)
        self.assertEqual(len(obs),3);self.assertTrue(w.runtime.applied)
        self.assertTrue(trunc[-1]);self.assertEqual(info,{})
        self.assertEqual([x['control_step'] for x in bridge.observer.frame_records],[0,1,2,3])
        with self.assertRaises(PairIntegrityError):bridge.step(np.zeros(7))

    def test_paired_prefix_mismatch_fails_before_execution(self):
        w=FakeWrapped()
        base={'init_state_sha256':'a'*64,'policy_seed':7,'policy_queries':[],
              'executed_actions':[{'policy_step':1,'action':[0.]*7}]}
        bridge=PairedEpisodeBridge(w,observer(),budget_controls=3,base_record=base)
        bridge.initialize(frame())
        with self.assertRaises(PairIntegrityError):bridge.step(np.ones(7))
        self.assertEqual(w.actions,[])
        bridge.step(np.zeros(7));self.assertEqual(bridge.prefix_checked_controls,1)

    def test_pre_event_vla_query_replays_saved_base_actions(self):
        w=FakeWrapped(); saved=np.zeros((5,7),dtype=np.float32)
        base={'init_state_sha256':'a'*64,'policy_seed':7,'executed_actions':[],
              'policy_queries':[{'policy_step':0,'actions':saved.tolist()}]}
        bridge=PairedEpisodeBridge(w,observer(),budget_controls=3,base_record=base)
        bridge.initialize(frame())
        class MustNotQuery:
            def predict(self,*args,**kwargs):raise AssertionError('pre-event model called')
        np.testing.assert_array_equal(bridge.query_actions(MustNotQuery(),bridge.last_obs),saved)
        self.assertEqual(w.queries[0]['source'],'control_replay')

    def test_official_manifest_validation_and_preregistered_counts(self):
        sys.path.insert(0,str(REPO/'external_readonly/libero_max_audit_20261007/src'))
        from libero_max.manifest import load_manifest
        for name,expected in [('sample160.json',160),('sample160_plus.json',120),('sample160_pro.json',40)]:
            parsed=load_manifest(PACKET/'isolated_eval'/name)
            self.assertEqual(len(parsed['cases']),expected)
        report=json.loads((PACKET/'selection_report.json').read_text())
        self.assertEqual(report['population_pairs'],800)
        self.assertEqual(set(report['event_counts'].values()),{20})


if __name__=='__main__':
    unittest.main(verbosity=2)
